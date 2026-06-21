"""Dictionary module — calls Hermes API Server for Cambridge-style definitions."""

import json
import re
import time
from openai import OpenAI
from config import HERMES_API_BASE, HERMES_API_KEY, HERMES_MODEL
from config import LOCAL_LLM_BASE, LOCAL_LLM_API_KEY, LOCAL_LLM_MODEL, LOCAL_LLM_ENABLED

# ── System prompt for structured dictionary output ──
SYSTEM_PROMPT = """You are a professional English-Chinese dictionary like Cambridge Dictionary.
Analyze the English word provided by the user and return ONLY a valid JSON object.

Rules:
- The word may be a single word (e.g. "apple") or a short phrase (e.g. "look up", "break down").
- If the word has multiple parts of speech (e.g. noun AND verb), include ONE definition for each.
- For the SAME part of speech, only provide the MOST COMMON single definition — do NOT list multiple sub-meanings.
- LIMIT the results array to at most 2 entries maximum.
- Phonetics should use IPA format inside slashes, e.g. /ˈæp.əl/.
- Definitions and examples must be natural English.
- Translations must be in Traditional Chinese (繁體中文).

Return ONLY the JSON with no markdown, no code fences, no extra text.

{
  "word": "the_word",
  "results": [
    {
      "part_of_speech": "noun | verb | adj | adv | etc.",
      "uk_phonetic": "/.../",
      "us_phonetic": "/.../",
      "definition_en": "English definition",
      "definition_zh": "繁體中文解釋",
      "example_en": "English example sentence",
      "example_zh": "繁體中文例句翻譯"
    }
  ]
}"""


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from text, even if surrounded by other content."""
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Find first { and last } in the text
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def query_local(word: str) -> dict | None:
    """Try Idea3 local LLM first."""
    if not LOCAL_LLM_ENABLED:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=LOCAL_LLM_API_KEY,
            base_url=LOCAL_LLM_BASE,
        )
        response = client.chat.completions.create(
            model=LOCAL_LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": word.strip()},
            ],
            temperature=0.2,
            max_tokens=1200,
            timeout=60,
        )
        content = response.choices[0].message.content
        if not content:
            return None
        data = _extract_json(content)
        if data and "results" in data and isinstance(data["results"], list):
            data["_source"] = "Idea3"
            return data
        return None
    except Exception as e:
        print(f"[dictionary] Local LLM failed for '{word}': {e}")
        return None


def query(word: str, max_retries: int = 2) -> dict | None:
    """Try local LLM first, fall back to Hermes API."""
    local_result = query_local(word)
    if local_result:
        return local_result
    return _query_hermes(word, max_retries)


def _query_hermes(word: str, max_retries: int = 2) -> dict | None:
    """Call Hermes API Server to look up a word."""
    client = OpenAI(
        api_key=HERMES_API_KEY,
        base_url=HERMES_API_BASE,
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=HERMES_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": word.strip()},
                ],
                temperature=0.2,
                max_tokens=1200,
                timeout=30,
            )

            content = response.choices[0].message.content
            if not content:
                if attempt < max_retries - 1:
                    print(f"[dictionary] Empty response for '{word}', retrying...")
                    time.sleep(1)
                    continue
                raise ValueError("Empty response from LLM after all retries")

            data = _extract_json(content)
            if data is None:
                if attempt < max_retries - 1:
                    print(f"[dictionary] Non-JSON response for '{word}', retrying...")
                    print(f"[dictionary] Raw: {content[:200]}")
                    time.sleep(1)
                    continue
                raise ValueError(f"Could not extract JSON from response: {content[:200]}")

            # Validate basic structure
            if "results" not in data or not isinstance(data["results"], list):
                if attempt < max_retries - 1:
                    print(f"[dictionary] Bad structure for '{word}', retrying...")
                    continue
                raise ValueError("Response missing 'results' array")

            data["_source"] = "OpenRouter"
            return data

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[dictionary] Attempt {attempt+1} failed for '{word}': {e}")
                time.sleep(2)
                continue
            print(f"[dictionary] All {max_retries} attempts failed for '{word}': {e}")
            return None

    return None