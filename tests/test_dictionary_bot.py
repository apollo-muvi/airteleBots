"""Tests for dictionary bots (volcabu-bot + apolloew-bot).

Tests shared pure-logic functions: _extract_json, _format_word_response,
_format_group, _is_authorized.
"""
import sys
from unittest.mock import patch, MagicMock
import pytest

from tests.conftest import (
    register_dictionary_bot_config,
    register_telegram_mock,
    register_database_mock,
    register_tts_handler_mock,
)
from tests.helpers import load_module


# ── _extract_json (in dictionary.py, identical in both bots) ─

@pytest.fixture(params=["volcabu-bot", "apolloew-bot"])
def dict_mod(request):
    """Load dictionary.py from each bot variant."""
    register_dictionary_bot_config()
    return load_module(request.param, "dictionary")


class TestExtractJson:
    def test_valid_json_direct(self, dict_mod):
        result = dict_mod._extract_json('{"word": "hello", "results": []}')
        assert result is not None
        assert result["word"] == "hello"

    def test_json_in_markdown_fence(self, dict_mod):
        result = dict_mod._extract_json('```json\n{"word": "hello"}\n```')
        assert result is not None
        assert result["word"] == "hello"

    def test_json_with_surrounding_text(self, dict_mod):
        result = dict_mod._extract_json('Here is: {"word": "test"} end.')
        assert result is not None
        assert result["word"] == "test"

    def test_malformed_json(self, dict_mod):
        assert dict_mod._extract_json("not json") is None

    def test_empty_string(self, dict_mod):
        assert dict_mod._extract_json("") is None

    def test_nested_json(self, dict_mod):
        result = dict_mod._extract_json(
            '{"word": "run", "results": [{"definition_en": "to move fast"}]}'
        )
        assert result is not None
        assert len(result["results"]) == 1

    def test_curly_braces_inside_text(self, dict_mod):
        result = dict_mod._extract_json("text with {curly} but not json")
        # May or may not parse — should not crash
        assert result is None or isinstance(result, dict)


# ── _is_authorized and formatting (in bot.py) ────────────────

@pytest.fixture(scope="module")
def volcabu_bot():
    register_dictionary_bot_config()
    register_telegram_mock()
    register_database_mock()
    register_tts_handler_mock()
    # Pre-load dictionary so bot.py can find it
    load_module("volcabu-bot", "dictionary")
    return load_module("volcabu-bot", "bot")


class TestIsAuthorized:
    def test_allow_all_true(self, volcabu_bot):
        import config
        config.ALLOW_ALL = True
        assert volcabu_bot._is_authorized(12345) is True

    def test_allow_all_false_user_in_list(self, volcabu_bot):
        import config
        config.ALLOW_ALL = False
        config.ALLOWED_USERS = ["12345"]
        assert volcabu_bot._is_authorized(12345) is True

    def test_allow_all_false_user_not_in_list(self, volcabu_bot):
        import config
        config.ALLOW_ALL = False
        config.ALLOWED_USERS = ["99999"]
        assert volcabu_bot._is_authorized(12345) is False

    def test_allow_all_false_empty_list(self, volcabu_bot):
        import config
        config.ALLOW_ALL = False
        config.ALLOWED_USERS = []
        assert volcabu_bot._is_authorized(1) is False


class TestFormatWordResponse:
    def test_basic_word_data(self, volcabu_bot):
        data = {
            "word": "Hello",
            "results": [{
                "part_of_speech": "interjection",
                "definition_en": "used as a greeting",
                "definition_zh": "你好",
            }],
        }
        result = volcabu_bot._format_word_response(data)
        assert "Hello" in result or "HELLO" in result
        assert "interjection" in result
        assert "used as a greeting" in result

    def test_with_phonetics(self, volcabu_bot):
        data = {
            "word": "Apple",
            "results": [{
                "part_of_speech": "noun",
                "uk_phonetic": "/ˈæp.əl/",
                "us_phonetic": "/ˈæp.əl/",
                "definition_en": "a fruit",
            }],
        }
        result = volcabu_bot._format_word_response(data)
        assert "/ˈæp.əl/" in result
        assert "UK:" in result

    def test_deduplicates_results(self, volcabu_bot):
        data = {
            "word": "Run",
            "results": [
                {"definition_en": "to move quickly", "part_of_speech": "verb"},
                {"definition_en": "to move quickly", "part_of_speech": "verb"},
                {"definition_en": "to manage", "part_of_speech": "verb"},
            ],
        }
        result = volcabu_bot._format_word_response(data)
        assert result.count("to move quickly") == 1
        assert result.count("to manage") == 1

    def test_empty_results(self, volcabu_bot):
        data = {"word": "Test", "results": []}
        result = volcabu_bot._format_word_response(data)
        assert result is not None

    def test_missing_fields(self, volcabu_bot):
        data = {"word": "Xyz", "results": [{"definition_en": "something"}]}
        result = volcabu_bot._format_word_response(data)
        assert result is not None

    def test_shows_source(self, volcabu_bot):
        data = {
            "word": "Test",
            "results": [{"definition_en": "a test"}],
            "_source": "Idea3",
        }
        result = volcabu_bot._format_word_response(data)
        assert "Idea3" in result


class TestFormatGroup:
    def test_basic_group(self, volcabu_bot):
        data = {
            "words": [
                {"word": "apple", "definition_en": "a fruit"},
                {"word": "book", "definition_en": "to read"},
            ],
        }
        result = volcabu_bot._format_group(data)
        assert "apple" in result.lower() or "Apple" in result
        assert "book" in result.lower() or "Book" in result

    def test_empty_words(self, volcabu_bot):
        assert volcabu_bot._format_group({"words": []}) is None

    def test_missing_words_key(self, volcabu_bot):
        assert volcabu_bot._format_group({}) is None

    def test_with_phonetics(self, volcabu_bot):
        data = {
            "words": [{
                "word": "hello",
                "uk_phonetic": "/həˈloʊ/",
                "definition_en": "a greeting",
            }],
        }
        result = volcabu_bot._format_group(data)
        assert "UK:" in result

    def test_multiple_words_separated(self, volcabu_bot):
        data = {
            "words": [
                {"word": "one", "definition_en": "first"},
                {"word": "two", "definition_en": "second"},
            ],
        }
        result = volcabu_bot._format_group(data)
        assert "one" in result.lower()
        assert "two" in result.lower()
