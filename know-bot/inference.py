"""
Inference module for Know_Bot — uses Hermes API to correct and
answer technical questions with structured information.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from config import HERMES_API_URL, HERMES_API_KEY

ASK_SYSTEM_PROMPT = """你是一個技術問答助手。使用者可能寫錯字或概念混淆，請依以下步驟回應：

**步驟 1：推理使用者真正的問題**
- 先分析使用者輸入，判斷他真正想問什麼
- 如果你發現其中有筆誤或概念混淆（例如 "interface" 其實是指 "inference"、"provider" 其實是指 "providers"），請指出並更正

**步驟 2：產生結構化技術說明**
以繁體中文輸出，涵蓋以下架構（如果適用於該主題）：

## 🔍 釐清與更正
- 使用者問的是：...（還原原始問題）
- 更正後的問題：...（修正後的版本）

## 📖 這是什麼
- 定義與核心概念
- 為什麼重要

## 🔧 使用流程
- 步驟式說明

## 💻 程式範例
- Python 範例（可執行片段）
- JavaScript / TypeScript 範例

## 🌐 REST API 概念
- 端點、認證、請求格式

## 📊 對照表（如適用）
如果跟 OpenAI API 或類似服務有可對照之處，條列異同

## ⚠️ 注意事項
- 適用情境、常見踩坑、最佳實踐

**格式要求：**
- 使用 Telegram 支援的 Markdown（**粗體**、`程式碼`、```區塊```、|表格|）
- 保持精簡但完整，長度控制在 2000 字以內
- 如果使用者輸入不是技術問題（例如閒聊），直接回答即可，不用強制套用上述架構
"""


async def ask_hermes(question: str) -> str:
    """Try local LLM first, fall back to Hermes API."""
    local_result = await ask_local_llm(question)
    if local_result:
        return local_result
    headers = {
        "Authorization": f"Bearer {HERMES_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "hermes-agent",
        "messages": [
            {"role": "system", "content": ASK_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "max_tokens": 2048,
        "temperature": 0.5,
    }

    url = f"{HERMES_API_URL.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except httpx.TimeoutException:
            return "⏱ Hermes API 請求超時，請稍後再試。"
        except httpx.HTTPStatusError as e:
            return f"❌ Hermes API 錯誤 ({e.response.status_code})：{e.response.text[:200]}"
        except Exception as e:
            return f"❌ 請求失敗：{str(e)[:200]}"

async def ask_local_llm(question: str) -> str:
    """Use Idea3's local LLM via Ollama OpenAI-compatible API."""
    from config import LOCAL_LLM_BASE, LOCAL_LLM_API_KEY, LOCAL_LLM_MODEL, LOCAL_LLM_ENABLED
    if not LOCAL_LLM_ENABLED:
        return ""
    headers = {
        "Authorization": f"Bearer {LOCAL_LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LOCAL_LLM_MODEL,
        "messages": [
            {"role": "system", "content": ASK_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{LOCAL_LLM_BASE}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Local LLM error: {e}")
        return ""
