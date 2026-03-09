import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL
import asyncio
import logging

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)


async def ask_employee(system_prompt: str, conversation_context: str, task: str) -> str:
    """
    呼叫 Gemini，扮演特定員工角色回應
    system_prompt: 員工個性設定
    conversation_context: 目前會議的對話記錄
    task: 這輪要做什麼（第幾輪、任務說明）
    """
    full_prompt = f"""{system_prompt}

━━━ 本次會議記錄 ━━━
{conversation_context if conversation_context else "（會議剛開始，尚無其他發言）"}

━━━ 你的任務 ━━━
{task}

請依照你的個性和專業，回應以上情境。記住發言規則。
"""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(full_prompt)
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        # Fallback if model name doesn't work
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(full_prompt)
            )
            return response.text.strip()
        except Exception as e2:
            logger.error(f"Gemini fallback error: {e2}")
            return f"（系統錯誤，請稍後重試：{str(e2)[:50]}）"


async def check_boss_intent(text: str) -> str:
    """
    判斷老闆的意圖：要參加會議 or 讓AI自動處理
    回傳 "join" / "auto" / "unknown"
    """
    prompt = f"""使用者說了：「{text}」

判斷這個人是否要「參加今天的會議」。

如果他的意思是要參加（例如：等我、我來、有空、要、好、我參加、等一下、來開會等），回覆：join
如果他的意思是讓AI自動處理（例如：你們決定、自動、不用等我、ok你們開吧等），回覆：auto
如果不確定，回覆：unknown

只回覆一個單字：join 或 auto 或 unknown"""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt)
        )
        result = response.text.strip().lower()
        if "join" in result:
            return "join"
        elif "auto" in result:
            return "auto"
        return "unknown"
    except:
        return "unknown"


async def check_budget_mention(text: str) -> bool:
    """
    判斷提案中是否涉及預算行為
    回傳 True = 有預算，需請示老闆
    """
    prompt = f"""以下是行銷會議中的一段發言：
「{text}」

判斷這段發言是否涉及以下任何「需要花錢」的行銷行為：
- 廣告投放（FB Ads、Google Ads、IG廣告）
- KOL/網紅合作
- 付費推廣
- 購買素材、工具、授權
- 贊助活動
- 任何提到「預算」「費用」「花費」「投資」「付費」

如果有，回覆：yes
如果沒有（純有機內容、策略討論、文案設計），回覆：no

只回覆 yes 或 no"""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt)
        )
        return "yes" in response.text.strip().lower()
    except:
        return False
