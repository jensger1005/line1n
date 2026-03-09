import asyncio
import gspread
import json
import os
import logging
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1tkbHI2c9JPXoLw_zsMWfYL34-IwQ83XtfzBe-PqkBYY"

SHEET_INPUT   = "輸入資料"
SHEET_RECORDS = "開會記錄"
SHEET_TASKS   = "任務包"


def _get_spreadsheet():
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 未設定")
    creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


# ── 同步版（在 executor 中執行）────────────────────

def _sync_read_input_data() -> str:
    sh = _get_spreadsheet()
    ws = sh.worksheet(SHEET_INPUT)
    rows = ws.get_all_values()
    if not rows:
        return "（輸入資料分頁為空）"
    lines = []
    for row in rows:
        parts = [cell.strip() for cell in row if cell.strip()]
        if parts:
            lines.append("　".join(parts))
    return "\n".join(lines) if lines else "（無有效資料）"


def _sync_append_meeting_record(date_str: str, time_str: str, mode: str, conversation: str):
    sh = _get_spreadsheet()
    ws = sh.worksheet(SHEET_RECORDS)
    ws.append_row([date_str, time_str, mode, conversation])


def _sync_append_task_package(date_str: str, time_str: str, plan: str, conclusion: str, task_content: str):
    sh = _get_spreadsheet()
    ws = sh.worksheet(SHEET_TASKS)
    ws.append_row([date_str, time_str, f"方案{plan}", conclusion, task_content])


# ── 非同步版（供 meeting_engine 呼叫）───────────────

async def read_input_data() -> str:
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_read_input_data)
    except Exception as e:
        logger.error(f"讀取輸入資料失敗：{e}")
        return "（無法讀取輸入資料，使用預設模式）"


async def save_meeting_record(date_str: str, time_str: str, mode: str, conversation: str):
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _sync_append_meeting_record, date_str, time_str, mode, conversation
        )
        logger.info("開會記錄已儲存至 Google Sheets")
    except Exception as e:
        logger.error(f"儲存開會記錄失敗：{e}")


async def save_task_package(date_str: str, time_str: str, plan: str, conclusion: str, task_content: str):
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _sync_append_task_package, date_str, time_str, plan, conclusion, task_content
        )
        logger.info("任務包已儲存至 Google Sheets")
    except Exception as e:
        logger.error(f"儲存任務包失敗：{e}")
