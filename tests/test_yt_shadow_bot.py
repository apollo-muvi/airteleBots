"""Tests for yt-shadow-bot (YouTube Shadow Transcript Bot).

Tests pure-logic functions: video ID extraction, timestamp formatting,
URL detection, filename cleaning, text splitting.
"""
import sys
import pytest
from unittest.mock import patch

from tests.conftest import register_yt_shadow_bot_config, register_telegram_mock
from tests.helpers import load_module


@pytest.fixture(scope="module")
def transcript():
    return load_module("yt-shadow-bot", "transcript")


@pytest.fixture(scope="module")
def bot():
    register_yt_shadow_bot_config()
    register_telegram_mock()
    return load_module("yt-shadow-bot", "bot")


# ── transcript.py ────────────────────────────────────────────

class TestExtractVideoId:
    def test_full_youtube_url(self, transcript):
        assert transcript.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be(self, transcript):
        assert transcript.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts(self, transcript):
        assert transcript.extract_video_id("https://youtube.com/shorts/abcDEF12345") == "abcDEF12345"

    def test_embed(self, transcript):
        assert transcript.extract_video_id("https://youtube.com/embed/xyz78901234") == "xyz78901234"

    def test_live(self, transcript):
        assert transcript.extract_video_id("https://youtube.com/live/lmn45678901") == "lmn45678901"

    def test_bare_id(self, transcript):
        assert transcript.extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_with_timestamp_param(self, transcript):
        vid = "https://youtube.com/watch?v=abc123DEF45&t=30s"
        assert transcript.extract_video_id(vid) == "abc123DEF45"

    def test_non_youtube_returns_as_is(self, transcript):
        assert transcript.extract_video_id("not-a-video-id") == "not-a-video-id"

    def test_empty_string(self, transcript):
        assert transcript.extract_video_id("") == ""

    def test_11_char_mixed(self, transcript):
        assert transcript.extract_video_id("aB3-xY7_zQp") == "aB3-xY7_zQp"


class TestFormatTs:
    def test_zero(self, transcript):
        assert transcript.format_ts(0) == "00:00"

    def test_under_minute(self, transcript):
        assert transcript.format_ts(45) == "00:45"

    def test_exact_minute(self, transcript):
        assert transcript.format_ts(60) == "01:00"

    def test_one_hour(self, transcript):
        assert transcript.format_ts(3600) == "1:00:00"

    def test_hour_minute_second(self, transcript):
        assert transcript.format_ts(3661) == "1:01:01"

    def test_float_truncation(self, transcript):
        assert transcript.format_ts(90.7) == "01:30"

    def test_large_value(self, transcript):
        assert transcript.format_ts(7384) == "2:03:04"


# ── bot.py helpers ───────────────────────────────────────────

class TestIsYoutubeUrl:
    def test_standard(self, bot):
        assert bot._is_youtube_url("https://youtube.com/watch?v=abc") is True

    def test_youtu_be(self, bot):
        assert bot._is_youtube_url("https://youtu.be/abc") is True

    def test_shorts(self, bot):
        assert bot._is_youtube_url("https://youtube.com/shorts/abc") is True

    def test_embed(self, bot):
        assert bot._is_youtube_url("https://youtube.com/embed/abc") is True

    def test_live(self, bot):
        assert bot._is_youtube_url("https://youtube.com/live/abc") is True

    def test_non_youtube(self, bot):
        assert bot._is_youtube_url("https://example.com") is False

    def test_empty(self, bot):
        assert bot._is_youtube_url("") is False


class TestCleanFilename:
    def test_simple(self, bot):
        assert bot._clean_filename("Hello World") == "Hello_World"

    def test_illegal_chars(self, bot):
        assert bot._clean_filename('file:name?*<>"|') == "file_name"

    def test_chinese(self, bot):
        result = bot._clean_filename("我的影片")
        assert result  # not empty

    def test_collapse_underscores(self, bot):
        assert bot._clean_filename("a   b___c") == "a_b_c"

    def test_strip_leading_trailing(self, bot):
        assert bot._clean_filename("__hello__") == "hello"

    def test_all_illegal(self, bot):
        assert bot._clean_filename('\\/:*?"<>|') == "transcript"

    def test_empty(self, bot):
        assert bot._clean_filename("") == "transcript"


class TestSplitText:
    def test_under_limit(self, bot):
        assert bot._split_text("hello", 100) == ["hello"]

    def test_empty(self, bot):
        assert bot._split_text("", 100) == [""]

    def test_chunks_respect_max_len(self, bot):
        text = "line1\nline2\nline3\nline4"
        chunks = bot._split_text(text, 15)
        assert len(chunks) > 1
        for c in chunks[:-1]:
            assert len(c) <= 15

    def test_preserves_lines(self, bot):
        text = "a\nb\nc"
        assert bot._split_text(text, 100) == [text]
