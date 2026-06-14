"""TTS module — generate pronunciation audio files using Google TTS."""

import os
from gtts import gTTS
from config import TTS_LANG, TTS_TLD_UK, TTS_TLD_US

# Directory for audio files
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "data", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


def _tts(word: str, tld: str, label: str) -> str | None:
    """Generate a TTS audio file for a word with given accent.
    
    Returns file path, or None on failure.
    """
    filename = f"{word}_{label}.ogg"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath):
        return filepath

    try:
        tts = gTTS(text=word, lang=TTS_LANG, tld=tld, slow=False)
        tts.save(filepath)
        return filepath
    except Exception as e:
        print(f"[tts] Error generating {label} audio for '{word}': {e}")
        return None


def generate_pronunciation(word: str) -> dict[str, str | None]:
    """Generate both UK and US pronunciation audio files.
    
    Returns dict with 'uk' and 'us' keys mapping to file paths (or None).
    """
    return {
        "uk": _tts(word, TTS_TLD_UK, "uk"),
        "us": _tts(word, TTS_TLD_US, "us"),
    }