import asyncio
import json
import os
import logging
from datetime import datetime, date
import pytz

from config import (
    EMPLOYEES, DIRECTOR, THINK_DELAY_SECONDS,
    DECISION_DEADLINE_MINUTES, TIMEZONE
)
from gemini_client import ask_employee, check_budget_mention
from line_client import (
    send_line_message, format_employee_message,
    format_director_message, format_system_message
)

logger = logging.getLogger(__name__)

SUMMARY_FILE = "meeting_summaries.json"
tz = pytz.timezone(TIMEZONE)


# ── 記憶體狀態 ────────────────────────────────────
class MeetingState:
    def __init__(self):
        self.group_id: str = None
        self.boss_joining: bool = False
        self.waiting_for_boss_response: bool = False
        self.meeting_in_progress: bool = False
        self.awaiting_boss_decision: bool = False
        self.current_meeting_summary: str = ""
        self.proposal_a: str = ""
        self.proposal_b: str = ""
        self.budget_flag: bool = False

state = MeetingState()


# ── 記憶：讀寫昨日摘要 ────────────────────────────
def load_recent_summaries(days: int = 3) -> str:
    """讀取最近幾天的會議摘要"""
    if not os.path.exists(SUMMARY_FILE):
        return "（尚無歷史記錄，這是第一次會議）"

    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    recent = list(summaries.items())[-days:]
    if not recent:
        return "（尚無歷史記錄）"

    result = []
    for date_str, summary in recent:
        result.append(f"📅 {date_str}\n{summary}")
    return "\n\n".join(result)


def save_meeting_summary(summary: str):
    """儲存今日會議摘要"""
    today = date.today().strftime("%Y-%m-%d")

    if os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            summaries = json.load(f)
    else:
        summaries = {}

    summaries[today] = summary

    # 只保留最近60天
    if len(summaries) > 60:
        oldest_key = list(summaries.keys())[0]
        del summaries[oldest_key]

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)


# ── 主要會議流程 ──────────────────────────────────
async def run_morning_meeting(group_id: str, boss_joining: bool):
    """執行完整的早會流程"""
    if state.meeting_in_progress:
        logger.warning("Meeting already in progress, skipping")
        return

    state.meeting_in_progress = True
    state.group_id = group_id
    conversation_log = []  # 完整對話記錄
    budget_triggered = False

    try:
        now = datetime.now(tz).strftime("%H:%M")
        mode_text = "老闆參與模式 👑" if boss_joining else "自動決策模式 🤖"

        await send_line_message(group_id, format_system_message(
            f"早會開始｜{now}\n模式：{mode_text}\n"
            f"{'─' * 20}\n"
            f"今日議程：行銷策略與內容規劃\n"
            f"預計時長：15分鐘"
        ))

        await asyncio.sleep(3)

        # 載入歷史記憶
        recent_history = load_recent_summaries(3)

        # ── 第一輪：數據師開場 ────────────────────
        await send_line_message(group_id, "💭 數據師正在整理報告...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        data_task = f"""現在是早會第一輪，由你開場。
任務：報告近期數據表現，並基於數據提出今日行銷的重點方向建議。

近期會議記錄參考：
{recent_history}

注意：這是第一輪，不需要引用同事觀點，直接報數據和建議即可。"""

        data_response = await ask_employee(
            EMPLOYEES["數據師"]["system_prompt"],
            "",
            data_task
        )
        conversation_log.append(f"王雅婷(數據師)：{data_response}")

        await send_line_message(group_id, format_employee_message(
            "王雅婷", "數據師", "📊", data_response
        ))

        # ── 第一輪：策略師回應數據 ────────────────
        await send_line_message(group_id, "💭 策略師正在思考...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        context_so_far = "\n\n".join(conversation_log)
        strategy_task = f"""現在是早會第一輪，你在數據師之後發言。
任務：根據數據師的報告，提出今日2個行銷策略方向。
必須引用數據師的觀點，且提出與數據師不同角度的見解。"""

        strategy_response = await ask_employee(
            EMPLOYEES["策略師"]["system_prompt"],
            context_so_far,
            strategy_task
        )
        conversation_log.append(f"林建宏(策略師)：{strategy_response}")

        await send_line_message(group_id, format_employee_message(
            "林建宏", "策略師", "🎯", strategy_response
        ))

        # ── 第二輪：文案師 ────────────────────────
        await send_line_message(group_id, "💭 文案師正在構思...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        context_so_far = "\n\n".join(conversation_log)
        copy_task = f"""現在是早會第二輪，文案師發言。
任務：根據策略師的方向，提出2個不同風格的文案方向（附示例句），
必須引用策略師或數據師的觀點，並說明你的文案如何服務策略目標。"""

        copy_response = await ask_employee(
            EMPLOYEES["文案師"]["system_prompt"],
            context_so_far,
            copy_task
        )
        conversation_log.append(f"陳柔安(文案師)：{copy_response}")

        await send_line_message(group_id, format_employee_message(
            "陳柔安", "文案師", "✍️", copy_response
        ))

        # ── 第二輪：設計師 ────────────────────────
        await send_line_message(group_id, "💭 設計師正在規劃視覺...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        context_so_far = "\n\n".join(conversation_log)
        design_task = f"""現在是早會第二輪，設計師發言。
任務：針對文案師的兩個方向，提出對應的視覺概念（色調/構圖/情緒），
必須引用文案師的觀點，可以指出文案和視覺之間的衝突。"""

        design_response = await ask_employee(
            EMPLOYEES["設計師"]["system_prompt"],
            context_so_far,
            design_task
        )
        conversation_log.append(f"張偉誠(設計師)：{design_response}")

        await send_line_message(group_id, format_employee_message(
            "張偉誠", "設計師", "🎨", design_response
        ))

        # ── 第三輪：數據師回應衝突 ────────────────
        await send_line_message(group_id, "💭 數據師正在補充...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        context_so_far = "\n\n".join(conversation_log)
        data_round2_task = f"""現在是第三輪，你要回應剛才的討論。
任務：針對策略師的方向，補充數據支撐或提出質疑，
特別是哪個方向數據較支持，哪個方向風險較高。
必須引用策略師的某個具體觀點。"""

        data_round2_response = await ask_employee(
            EMPLOYEES["數據師"]["system_prompt"],
            context_so_far,
            data_round2_task
        )
        conversation_log.append(f"王雅婷(數據師)再次發言：{data_round2_response}")

        await send_line_message(group_id, format_employee_message(
            "王雅婷", "數據師", "📊", data_round2_response
        ))

        # ── 預算檢查 ──────────────────────────────
        full_context = "\n".join(conversation_log)
        budget_triggered = await check_budget_mention(full_context)

        if budget_triggered:
            state.budget_flag = True
            await send_line_message(group_id, format_system_message(
                "⚠️ 偵測到本次討論涉及付費行銷行為\n此決策需要老闆授權\n已暫停自動決策，等待老闆指示"
            ))
            await asyncio.sleep(3)

        # ── 總監整合結論 ──────────────────────────
        await send_line_message(group_id, "💭 總監正在整合結論...")
        await asyncio.sleep(THINK_DELAY_SECONDS)

        context_so_far = "\n\n".join(conversation_log)

        if boss_joining or budget_triggered:
            director_task = f"""現在是早會結尾，你要給出整合結論。
模式：老闆參與決策（或涉及預算需老闆授權）

任務：
1. 列出本次討論的1-2個主要衝突點
2. 說明你的整合邏輯
3. 提出「方案A」和「方案B」供老闆選擇
4. 結尾說：「請老闆在今日10:00前回覆選擇，否則自動執行方案A」

近期歷史參考：
{recent_history}"""
        else:
            director_task = f"""現在是早會結尾，你要給出整合結論。
模式：自動決策（老闆未參與）

任務：
1. 列出本次討論的1-2個主要衝突點
2. 說明你的整合邏輯
3. 宣布「今日執行方案」（選一個最佳方案，說明原因）
4. 結尾說：「⚠️ 老闆如有異議請在09:30前回覆，否則將自動開始執行」

近期歷史參考：
{recent_history}"""

        director_response = await ask_employee(
            DIRECTOR["system_prompt"],
            context_so_far,
            director_task
        )

        await send_line_message(group_id, format_director_message(director_response))

        # 儲存今日提案給後續決策用
        state.current_meeting_summary = director_response
        state.awaiting_boss_decision = boss_joining or budget_triggered

        # 儲存會議記錄
        full_log = f"【開會模式：{'有人' if boss_joining else '自動'}】\n\n" + \
                   "\n\n".join(conversation_log) + \
                   f"\n\n【總監結論】\n{director_response}"
        save_meeting_summary(full_log)

        # 自動模式：提醒異議時間
        if not boss_joining and not budget_triggered:
            await asyncio.sleep(5)
            deadline_time = datetime.now(tz).strftime("%H:%M")
            # Calculate 15 min later
            import datetime as dt
            future = datetime.now(tz) + dt.timedelta(minutes=DECISION_DEADLINE_MINUTES)
            deadline = future.strftime("%H:%M")
            await send_line_message(group_id, format_system_message(
                f"📋 今日任務包將於 {deadline} 產出\n"
                f"如需修改請在此之前回覆：\n"
                f"「停止」→ 暫停執行\n"
                f"「改B」→ 切換備選方案\n"
                f"「修改：[你的指示]」→ 自訂調整"
            ))

    except Exception as e:
        logger.error(f"Meeting error: {e}")
        await send_line_message(group_id, format_system_message(
            f"⚠️ 會議發生錯誤，請聯繫管理員\n錯誤：{str(e)[:100]}"
        ))
    finally:
        state.meeting_in_progress = False


# ── 老闆決策處理 ──────────────────────────────────
async def handle_boss_decision(group_id: str, text: str):
    """處理老闆在會議後的決策"""
    text_lower = text.lower()

    if "停止" in text or "stop" in text_lower:
        state.awaiting_boss_decision = False
        await send_line_message(group_id, format_director_message(
            "收到，今日執行暫停。\n請告訴我新的方向，我來重新安排。"
        ))
        return True

    if "改b" in text_lower or "選b" in text_lower or "方案b" in text_lower:
        state.awaiting_boss_decision = False
        await send_line_message(group_id, format_director_message(
            "✅ 收到！執行方案B。\n正在產出今日任務包..."
        ))
        await asyncio.sleep(2)
        await produce_task_package(group_id, "B")
        return True

    if "選a" in text_lower or "方案a" in text_lower or "a" == text_lower.strip():
        state.awaiting_boss_decision = False
        await send_line_message(group_id, format_director_message(
            "✅ 收到！執行方案A。\n正在產出今日任務包..."
        ))
        await asyncio.sleep(2)
        await produce_task_package(group_id, "A")
        return True

    if "修改" in text or text.startswith("改"):
        state.awaiting_boss_decision = False
        instruction = text.replace("修改：", "").replace("改", "").strip()
        await send_line_message(group_id, format_director_message(
            f"✅ 收到調整指示：「{instruction}」\n正在重新規劃..."
        ))
        return True

    return False


async def produce_task_package(group_id: str, plan: str = "A"):
    """產出今日任務包"""
    today = date.today().strftime("%Y-%m-%d")
    now = datetime.now(tz).strftime("%H:%M")

    task_message = (
        f"📦 今日任務包｜{today}\n"
        f"{'═' * 25}\n"
        f"執行方案：方案{plan}\n"
        f"產出時間：{now}\n"
        f"{'─' * 25}\n"
        f"📱 社群小編 任務：\n"
        f"→ 依據今日文案方向撰寫正式貼文\n"
        f"→ 平台：IG + FB\n"
        f"→ 發布時間：18:00\n\n"
        f"🎨 視覺 任務：\n"
        f"→ 依據今日視覺方向製作圖片\n"
        f"→ 規格：1:1 + 9:16\n\n"
        f"{'─' * 25}\n"
        f"✅ 任務已派發，執行手開始作業"
    )

    await send_line_message(group_id, task_message)
