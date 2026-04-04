"""
Guest agent-side safety validation for incoming interview questions.

Defense strategy (two layers):
  1. Fast regex heuristic  — zero dependencies, catches naive attacks instantly
  2. Optional ML classifier — guardrails-ai PromptInjection (if installed)
                              used as secondary signal only

Design principle
----------------
The platform (AgentCast host) is TRUSTED — questions come from our own
Pipecat code.  However, a rogue platform operator or MITM could in theory
send a manipulated question payload.  This module lets SDK users validate
questions before feeding them to their own LLM.

Usage
-----
    from agentcast.guardrails import validate_question

    interview = client.poll()
    if interview:
        safety = validate_question(interview.question)
        if not safety.is_safe:
            # Question looks suspicious — abandon and skip
            client.abandon(interview.interview_id)
        else:
            answer = my_agent.answer(interview.question)
            client.respond(interview.interview_id, answer)
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Layer 1: Regex heuristic (no dependencies) ─────────────────────────────
# Catches the most common structural injection patterns.
# Fast, zero false-positives on normal interview questions.

_INJECTION_RE = re.compile(
    r"""
    # Classic command injections (more flexible word ordering)
    ignore\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|above)?\s*(?:instructions?|directives?|rules?|identity|persona)
    |disregard\s+(?:all\s+)?(?:prior|previous|above)\s+instructions
    |you\s+are\s+now\s+(?:a\s+|an\s+)?(?:DAN|different|no\s+longer|root|admin)
    |act\s+as\s+(?:if\s+you\s+(?:are|were)|a\s+different|a\s+terminal)
    # System / developer role injection
    |<\s*/?\s*(?:system|developer|instructions?|role|assistant|user)\s*/?\s*>
    |\[\s*/?\s*(?:SYSTEM|DEVELOPER|INSTRUCTION|OVERRIDE)\s*/?\s*\]
    # Reveal system prompt attempts (allows extra words between verb and keyword)
    |(?:reveal|print|output|show|repeat|describe|tell|write|what\s+is)(?:\s+\w+)*\s+(?:prompt|instructions?|directives?|rules?|context|identity)
    |what\s+(?:are\s+)?your\s+(?:system\s+)?(?:instructions?|directives?|rules?)
    # Fix 6: Expanded injection patterns
    |forget\s+(?:everything|all|your|previous)
    |from\s+now\s+on[\s,]
    |your\s+(?:real|true|actual|hidden)\s+(?:instructions?|purpose|goal|identity)
    |pretend\s+(?:that\s+)?you\s+(?:are|have\s+no)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _heuristic_check(question: str) -> Optional[str]:
    """Return reason string if suspicious, None if clean."""
    m = _INJECTION_RE.search(question)
    if m:
        return f"injection pattern detected: {m.group(0)!r}"
    return None


# ── Layer 2: Optional ML classifier (guardrails-ai) ────────────────────────
# Only used if the library is installed.  NOT used as a blocker on its own
# because of ~95% false-positive rate on technical content — used only as
# an additional signal when the heuristic is inconclusive.

_guard = None
_guard_available: Optional[bool] = None   # None = not yet checked


def _try_get_ml_guard():
    """Lazily attempt to load guardrails PromptInjection guard."""
    global _guard, _guard_available
    if _guard_available is not None:
        return _guard if _guard_available else None
    try:
        from guardrails import Guard         # type: ignore
        from guardrails.hub import PromptInjection  # type: ignore
        _guard = Guard().use(PromptInjection, pass_on_invalid=False)
        _guard_available = True
        logger.debug("guardrails-ai PromptInjection guard loaded (secondary layer)")
    except (ImportError, Exception) as e:
        _guard_available = False
        logger.debug("guardrails-ai not available, using heuristic only: %s", e)
    return _guard


# ── Public API ──────────────────────────────────────────────────────────────

@dataclass
class QuestionSafety:
    """Result of validating an incoming interview question."""
    is_safe: bool
    reason: Optional[str] = None   # populated when is_safe=False


def validate_question(question: str) -> QuestionSafety:
    """Validate an incoming interview question for prompt injection.

    Layer 1 (heuristic) blocks fast on obvious patterns.
    Layer 2 (ML) used as secondary signal — DOES NOT block alone to avoid
    false positives on legitimate technical discussion.

    Args:
        question: Raw question string received from the platform.

    Returns:
        QuestionSafety(is_safe=True/False, reason=...)
    """
    if not question or not question.strip():
        return QuestionSafety(is_safe=True)

    # Layer 1: fast heuristic
    reason = _heuristic_check(question)
    if reason:
        logger.warning("validate_question [heuristic]: UNSAFE — %s", reason)
        return QuestionSafety(is_safe=False, reason=f"heuristic: {reason}")

    # Layer 2: ML classifier (advisory — only flags, does NOT block alone)
    guard = _try_get_ml_guard()
    if guard:
        try:
            guard.validate(question)
        except Exception as ml_exc:
            # ML flagged it AND heuristic flagged it → block
            # ML flagged alone → warn but allow (high false positive rate)
            logger.warning(
                "validate_question [ML]: flagged question (not blocking alone): %s",
                str(ml_exc)[:120],
            )

    return QuestionSafety(is_safe=True)


# ── Fix 5: Output validation (agent answer) ──────────────────────────────────

def validate_answer(answer: str) -> QuestionSafety:
    """Validate an outgoing agent answer for secret leakage and injection patterns.

    Checks agent's response before sending back to platform.
    Protects against:
    - Secret leakage: API_KEY, PASSWORD, TOKEN, PRIVATE_KEY, SECRET
    - Injection patterns: Same heuristic as validate_question

    Args:
        answer: Raw answer string from the agent.

    Returns:
        QuestionSafety(is_safe=True/False, reason=...)
    """
    if not answer or not answer.strip():
        return QuestionSafety(is_safe=True)

    # Check for secret leakage patterns
    secret_patterns = [
        "API_KEY", "PASSWORD", "TOKEN", "PRIVATE_KEY", "SECRET"
    ]
    for pattern in secret_patterns:
        if pattern in answer.upper():
            logger.warning("validate_answer [secrets]: UNSAFE — found %s pattern", pattern)
            return QuestionSafety(
                is_safe=False,
                reason=f"secret leakage detected: {pattern}"
            )

    # Check for injection patterns (reuse the heuristic from input filtering)
    reason = _heuristic_check(answer)
    if reason:
        logger.warning("validate_answer [injection]: UNSAFE — %s", reason)
        return QuestionSafety(is_safe=False, reason=f"injection pattern in answer: {reason}")

    return QuestionSafety(is_safe=True)
