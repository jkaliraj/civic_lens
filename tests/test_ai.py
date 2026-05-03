"""Unit tests for CivicLens Gemini AI module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ai.gemini import _clean_json, SYSTEM_INSTRUCTION


class TestCleanJson:
    """Test suite for the _clean_json helper."""

    def test_plain_json(self):
        """Plain JSON string should be parsed correctly."""
        raw = '{"key": "value"}'
        assert _clean_json(raw) == {"key": "value"}

    def test_with_fences(self):
        """JSON wrapped in ```json fences should be extracted."""
        raw = '```json\n{"key": "value"}\n```'
        assert _clean_json(raw) == {"key": "value"}

    def test_with_fences_no_lang(self):
        """JSON wrapped in plain ``` fences should be extracted."""
        raw = '```\n[1, 2, 3]\n```'
        assert _clean_json(raw) == [1, 2, 3]

    def test_invalid_json_raises(self):
        """Non-JSON text should raise JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            _clean_json("not json at all")

    def test_nested_objects(self):
        """Nested JSON structures should parse correctly."""
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = _clean_json(raw)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_array_of_objects(self):
        """Array of objects should parse correctly."""
        raw = '[{"a": 1}, {"b": 2}]'
        result = _clean_json(raw)
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be stripped before parsing."""
        raw = '  \n  {"key": "value"}  \n  '
        assert _clean_json(raw) == {"key": "value"}

    def test_empty_object(self):
        """Empty JSON object should parse correctly."""
        assert _clean_json("{}") == {}

    def test_empty_array(self):
        """Empty JSON array should parse correctly."""
        assert _clean_json("[]") == []


class TestSystemInstruction:
    """Test suite for the Gemini system instruction prompt."""

    def test_is_non_partisan(self):
        """System instruction should enforce non-partisan behavior."""
        assert "non-partisan" in SYSTEM_INSTRUCTION
        assert "neutral" in SYSTEM_INSTRUCTION

    def test_contains_guidelines(self):
        """System instruction should contain educational guidelines."""
        assert "factual" in SYSTEM_INSTRUCTION
        assert "civic participation" in SYSTEM_INSTRUCTION

    def test_prevents_party_endorsement(self):
        """System instruction should redirect party-specific questions."""
        assert "party" in SYSTEM_INSTRUCTION.lower()
        assert "redirect" in SYSTEM_INSTRUCTION.lower()

    def test_uses_structured_formatting(self):
        """System instruction should encourage structured responses."""
        assert "bullet points" in SYSTEM_INSTRUCTION
        assert "numbered steps" in SYSTEM_INSTRUCTION

    def test_covers_global_elections(self):
        """System instruction should support global scope."""
        assert "global" in SYSTEM_INSTRUCTION.lower()

    def test_accessible_language(self):
        """System instruction should request accessible language."""
        assert "accessible language" in SYSTEM_INSTRUCTION
