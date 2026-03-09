import asyncio
import hashlib
import hmac
import base64
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, date

import httpx
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import (
    LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN,
    MEETING_HOUR, MEETING_MINUTE,
    REMINDER_HOUR, REMINDER_MINUTE,
    BOSS_RESPONSE_TIMEOUT_MINUTES, TIMEZONE
)
from gemini_client import check_boss_intent
from line_client import send_line_message, format_director_message, format_system_message
from meeting_engine import (
    state, run_morning_meeting,
    handle_boss_decision, produce_task_package
)

# ── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=tz)


# ── Scheduler Jobs ────────────────────────────────
async def job_morning_reminder():
    """08:55 總監晨間問候"""
    if not state.group_id:
        logger.warning("No group_id set yet, skipping reminder")
        return

    state.waiting_for_boss_response = True
    state.boss_joining = False  # Reset

    await send_line_message(state.group_id, format_director_message(
        f"早安！🌅\n"
        f"今天的行銷早會 09:00 開始\n\n"
        f"老闆，您今天要一起參與決策嗎？\n\n"
        f"💬 回覆「參加」或「等我」→ 有人模式\n"
        f"💬 回覆「自動」或不回應 → 自動決策\n\n"
        f"（5分鐘內未回應將自動開始）"
    ))

    # 5分鐘後如果還沒收到回應，自動進入自動模式
    await asyncio.sleep(BOSS_RESPONSE_TIMEOUT_MINUTES * 60)
    if state.waiting_for_boss_response:
        state.waiting_for_boss_response = False
        logger.info("Boss did not respond to reminder, will use auto mode")


async def job_start_meeting():
    """09:00 開始會議"""
    if not state.group_id:
        logger.warning("No group_id set yet, skipping meeting")
        return

    # 如果還在等老闆回覆，強制開始（自動模式）
    if state.waiting_for_boss_response:
        state.waiting_for_boss_response = False
        state.boss_joining = False

    boss_joining = state.boss_joining
    group_id = state.group_id

    logger.info(f"Starting meeting. Boss joining: {boss_joining}")
    asyncio.create_task(run_morning_meeting(group_id, boss_joining))


# ── LINE Signature Verification ───────────────────
def verify_line_signature(body: bytes, signature: str) -> bool:
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ── Handle LINE Events ────────────────────────────
async def process_line_events(body: dict):
    """處理 LINE webhook 事件"""
    events = body.get("events", [])

    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        source_type = source.get("type")

        # 只處理群組訊息
        if source_type != "group":
            continue

        group_id = source.get("groupId")
        if group_id:
            state.group_id = group_id
            logger.info(f"Group ID captured: {group_id}")

        if event_type != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "").strip()
        if not text:
            continue

        # 忽略自己（LINE OA）發的訊息
        # LINE 不會把 bot 自己的訊息 webhook 回來，所以不需要特別處理

        logger.info(f"Received message: {text[:50]}")

        # ── 老闆回覆晨間問候 ─────────────────────
        if state.waiting_for_boss_response:
            intent = await check_boss_intent(text)
            if intent == "join":
                state.boss_joining = True
                state.waiting_for_boss_response = False
                await send_line_message(group_id, format_director_message(
                    "收到！老闆今天親自參與決策 💼\n09:00 見，我們一起開！"
                ))
                return
            elif intent == "auto":
                state.boss_joining = False
                state.waiting_for_boss_response = False
                await send_line_message(group_id, format_director_message(
                    "了解，今日採自動決策模式 🤖\n09:00 開始，結論出來會通知您"
                ))
                return

        # ── 老闆會議後決策 ───────────────────────
        if state.awaiting_boss_decision:
            handled = await handle_boss_decision(group_id, text)
            if handled:
                return

        # ── 特殊指令 ─────────────────────────────
        text_lower = text.lower()

        # 手動觸發開會（測試用）
        if text == "開會" or text == "/meeting":
            if not state.meeting_in_progress:
                await send_line_message(group_id, format_system_message(
                    "手動觸發開會模式（老闆參與）"
                ))
                asyncio.create_task(run_morning_meeting(group_id, boss_joining=True))
            else:
                await send_line_message(group_id, format_system_message(
                    "會議正在進行中，請稍候"
                ))
            return

        # 查看群組ID（設定用）
        if text == "/id" or text == "群組id":
            await send_line_message(group_id, format_system_message(
                f"群組 ID：\n{group_id}"
            ))
            return

        # 查看系統狀態
        if text == "/status" or text == "狀態":
            await send_line_message(group_id, format_system_message(
                f"系統狀態\n"
                f"{'─' * 20}\n"
                f"群組ID：{group_id[:10]}...\n"
                f"老闆參與今日：{'是' if state.boss_joining else '否'}\n"
                f"會議進行中：{'是' if state.meeting_in_progress else '否'}\n"
                f"等待老闆決策：{'是' if state.awaiting_boss_decision else '否'}\n"
                f"排程早會：{MEETING_HOUR:02d}:{MEETING_MINUTE:02d}\n"
                f"目前時間：{datetime.now(tz).strftime('%H:%M')}"
            ))
            return

        # 手動觸發任務包
        if text == "/task":
            await produce_task_package(group_id, "A")
            return


# ── App Lifespan ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動排程
    scheduler.add_job(
        job_morning_reminder,
        CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE),
        id="morning_reminder",
        replace_existing=True
    )
    scheduler.add_job(
        job_start_meeting,
        CronTrigger(hour=MEETING_HOUR, minute=MEETING_MINUTE),
        id="start_meeting",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started. Meeting at {MEETING_HOUR:02d}:{MEETING_MINUTE:02d} {TIMEZONE}")
    logger.info(f"Reminder at {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} {TIMEZONE}")

    yield

    scheduler.shutdown()
    logger.info("Scheduler stopped")


# ── FastAPI App ───────────────────────────────────
app = FastAPI(title="AI Meeting Bot", lifespan=lifespan)


@app.get("/")
async def health_check():
    return {
        "status": "running",
        "group_id": state.group_id,
        "meeting_in_progress": state.meeting_in_progress,
        "time": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    }


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body_bytes = await request.body()

    # Verify signature
    if not verify_line_signature(body_bytes, signature):
        logger.warning("Invalid LINE signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    body = json.loads(body_bytes)

    # Process in background to return 200 quickly
    background_tasks.add_task(process_line_events, body)

    return JSONResponse(content={"status": "ok"})


@app.get("/test-meeting")
async def test_meeting(background_tasks: BackgroundTasks):
    """測試用：手動觸發會議（不需要 LINE 訊息）"""
    if not state.group_id:
        return {"error": "No group_id set. Send a message to LINE group first."}

    if state.meeting_in_progress:
        return {"error": "Meeting already in progress"}

    background_tasks.add_task(run_morning_meeting, state.group_id, True)
    return {"status": "Meeting started", "mode": "boss_joining"}
