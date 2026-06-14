"""Dictionary module — calls Hermes API Server for Cambridge-style definitions."""

import json
import re
import time
from openai import OpenAI
from config import HERMES_API_BASE, HERMES_API_KEY, HERMES_MODEL

# ── System prompt for structured dictionary output ──
SYSTEM_PROMPT = """You are a professional English-Chinese dictionary like Cambridge Dictionary.
Analyze the English word provided by the user and return ONLY a valid JSON object.

Rules:
- The word may be a single word (e.g. "apple") or a short phrase (e.g. "look up", "break down").
- If the word has multiple meanings/parts of speech, include ALL of them in the results array.
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


def query(word: str, max_retries: int = 2) -> dict | None:
    """Call Hermes API Server to look up a word.
    
    Returns parsed JSON dict, or None on all failures.
    Retries once on parse failure.
    """
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

            return data

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[dictionary] Attempt {attempt+1} failed for '{word}': {e}")
                time.sleep(2)
                continue
            print(f"[dictionary] All {max_retries} attempts failed for '{word}': {e}")
            return None

    return None