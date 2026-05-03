"""Unit tests for CivicLens Gemini AI module."""
import json
from unittest.mock import MagicMock, patch

import pytest

from ai.gemini import _clean_json, SYSTEM_INSTRUCTION


def test_clean_json_plain():
    raw = '{"key": "value"}'
    assert _clean_json(raw) == {"key": "value"}


def test_clean_json_with_fences():
    raw = '```json\n{"key": "value"}\n```'
    assert _clean_json(raw) == {"key": "value"}


def test_clean_json_with_fences_no_lang():
    raw = '```\n[1, 2, 3]\n```'
    assert _clean_json(raw) == [1, 2, 3]


def test_clean_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        _clean_json("not json at all")


def test_system_instruction_is_non_partisan():
    assert "non-partisan" in SYSTEM_INSTRUCTION
    assert "neutral" in SYSTEM_INSTRUCTION


def test_system_instruction_contains_guidelines():
    assert "factual" in SYSTEM_INSTRUCTION
    assert "civic participation" in SYSTEM_INSTRUCTION
