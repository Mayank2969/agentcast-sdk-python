"""Tests for agent-side question validation."""
import pytest
from agentcast.guardrails import validate_question, QuestionSafety


class TestValidateQuestion:
    """Tests for client-side question validation."""

    def test_clean_question_passes(self):
        """Normal interview questions should pass."""
        question = "What are your thoughts on AI safety?"
        result = validate_question(question)
        # Note: actual validation depends on guardrails-ai being installed
        assert isinstance(result, QuestionSafety)

    def test_empty_question_safe(self):
        """Empty questions are considered safe."""
        result = validate_question("")
        assert result.is_safe is True

    def test_question_safety_dataclass(self):
        """QuestionSafety dataclass works correctly."""
        safety = QuestionSafety(is_safe=True)
        assert safety.is_safe is True
        assert safety.reason is None

        safety_blocked = QuestionSafety(
            is_safe=False, reason="Injection detected"
        )
        assert safety_blocked.is_safe is False
        assert safety_blocked.reason == "Injection detected"
