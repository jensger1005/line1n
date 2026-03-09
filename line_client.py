import httpx
import asyncio
import logging
from config import LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
}


async def send_line_message(group_id: str, text: str):
    """發送訊息到 LINE 群組"""
    payload = {
        "to": group_id,
        "messages": [{"type": "text", "text": text}]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(LINE_API_URL, headers=HEADERS, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"LINE API error: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"LINE send error: {e}")


async def send_with_typing_delay(group_id: str, text: str, delay: float = 0):
    """加上延遲後發送（模擬思考時間）"""
    if delay > 0:
        await asyncio.sleep(delay)
    await send_line_message(group_id, text)


def format_employee_message(employee_name: str, role: str, emoji: str, content: str) -> str:
    """格式化員工發言"""
    return f"{emoji}【{employee_name}｜{role}】\n{content}"


def format_director_message(content: str) -> str:
    """格式化總監發言"""
    return f"👔【陳志遠｜總監】\n{content}"


def format_system_message(content: str) -> str:
    """格式化系統訊息"""
    return f"🤖【系統通知】\n{content}"
