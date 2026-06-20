"""Tests for ytd-bot (YouTube Download Bot).

Tests pure-logic functions: URL/quality parsing, file path extraction.
"""
import re
from unittest.mock import patch, MagicMock
import pytest

from tests.conftest import register_ytd_bot_config
from tests.helpers import load_module


@pytest.fixture(scope="module")
def bot():
    register_ytd_bot_config()
    return load_module("ytd-bot", "bot")


# ── parse_quality ────────────────────────────────────────────

class TestParseQuality:
    def test_bare_url(self, bot):
        url, q, typ, send = bot.parse_quality("https://youtube.com/watch?v=abc")
        assert "youtube.com/watch?v=abc" in url
        assert q == "720"
        assert typ == "video"
        assert send is False

    def test_with_ytdn_prefix(self, bot):
        url, q, typ, send = bot.parse_quality("ytdn https://youtube.com/watch?v=abc")
        assert "youtube.com/watch?v=abc" in url

    def test_with_dpi_flag(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc --dpi:1080"
        )
        assert q == "1080"

    def test_audio_mode(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc audio"
        )
        assert typ == "audio"

    def test_audio_mode_mp3(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc mp3"
        )
        assert typ == "audio"

    def test_send_flag(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc --send"
        )
        assert send is True

    def test_best_quality(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc best"
        )
        assert q == "best"

    def test_dpi_best(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc --dpi:best"
        )
        assert q == "best"

    def test_bare_number(self, bot):
        url, q, typ, send = bot.parse_quality(
            "https://youtube.com/watch?v=abc 1080"
        )
        assert q == "1080"

    def test_no_url_returns_none(self, bot):
        url, q, typ, send = bot.parse_quality("just text")
        assert url is None

    def test_youtu_be_short(self, bot):
        url, q, typ, send = bot.parse_quality("https://youtu.be/abc123")
        assert "youtu.be/abc123" in url


# ── extract_filepath ─────────────────────────────────────────

class TestExtractFilepath:
    def test_merger_format(self, bot):
        assert bot.extract_filepath('[Merger] Merging formats into "/tmp/v.mp4"\n') == "/tmp/v.mp4"

    def test_download_destination(self, bot):
        assert bot.extract_filepath("[download] Destination: /tmp/v.mp4\n") == "/tmp/v.mp4"

    def test_no_match(self, bot):
        assert bot.extract_filepath("some random output") == ""

    def test_last_destination_when_multiple(self, bot):
        out = "[download] Destination: /tmp/part1.mp4\n" \
              "[download] Destination: /tmp/final.mp4\n"
        assert bot.extract_filepath(out) == "/tmp/final.mp4"


# ── build_args ───────────────────────────────────────────────

class TestBuildArgs:
    def test_video_basic(self, bot):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            args = bot.build_args("https://youtube.com/watch?v=abc", "720", "video")
        assert args[0] == "yt-dlp"
        assert "-f" in args

    def test_audio_mode_args(self, bot):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            args = bot.build_args("https://youtube.com/watch?v=abc", "720", "audio")
        assert "-x" in args
        assert "mp3" in args

    def test_best_quality_format(self, bot):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            args = bot.build_args("https://youtube.com/watch?v=abc", "best", "video")
        fmt_idx = args.index("-f") + 1
        assert "bestvideo" in args[fmt_idx]

    def test_ends_with_url(self, bot):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            args = bot.build_args("https://youtube.com/watch?v=abc", "720", "video")
        assert args[-1] == "https://youtube.com/watch?v=abc"
