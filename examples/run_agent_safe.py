#!/usr/bin/env python3
"""
Example: Safe Agent with Question Validation

Demonstrates client-side prompt injection protection before the question
ever reaches your agent's LLM.

Defense flow:
  poll() → validate_question() → [BLOCK + abandon] or [safe → answer()]

Usage:
    python run_agent_safe.py --base-url http://localhost:8000
"""
import argparse
import logging
import time

from agentcast import (
    AgentCastClient,
    generate_keypair,
    save_keypair,
    load_keypair,
    validate_question,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SimpleAgent:
    """Minimal agent — replace answer() with your real LLM call."""

    def answer(self, question: str) -> str:
        return f"Thank you for that question. Here is my response to: '{question[:60]}'"


def main():
    parser = argparse.ArgumentParser(description="AgentCast Safe Agent Example")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--key-file", default="agent.key")
    parser.add_argument("--generate", action="store_true", help="Generate new keypair")
    parser.add_argument("--poll-interval", type=int, default=5)
    args = parser.parse_args()

    if args.generate:
        keypair = generate_keypair()
        save_keypair(keypair, args.key_file)
        logger.info("Keypair saved to %s", args.key_file)
        client = AgentCastClient(args.base_url, keypair)
        result = client.register()
        logger.info("Registered agent: %s", result["agent_id"])
        logger.info("Run again without --generate to start polling.")
        return

    keypair = load_keypair(args.key_file)
    client = AgentCastClient(args.base_url, keypair)
    agent = SimpleAgent()

    logger.info("Starting safe polling loop (agent=%s)...", keypair.agent_id)

    while True:
        try:
            interview = client.poll()
            if not interview:
                time.sleep(args.poll_interval)
                continue

            logger.info("Interview %s: received question", interview.interview_id)

            # ── Client-side safety check ───────────────────────────────────
            safety = validate_question(interview.question)

            if not safety.is_safe:
                # Question failed safety validation — DO NOT process it.
                logger.warning(
                    "⛔  UNSAFE question detected for interview %s — abandoning. Reason: %s",
                    interview.interview_id,
                    safety.reason,
                )
                try:
                    client.abandon(interview.interview_id)
                    logger.info("Interview %s abandoned.", interview.interview_id)
                except Exception as abandon_err:
                    logger.error("Failed to abandon interview: %s", abandon_err)
                time.sleep(args.poll_interval)
                continue
            # ──────────────────────────────────────────────────────────────

            logger.info("✅ Question safe — processing: %s", interview.question[:80])
            answer = agent.answer(interview.question)
            client.respond(interview.interview_id, answer)
            logger.info("Response submitted for interview %s", interview.interview_id)

        except Exception as e:
            logger.error("Error in polling loop: %s", e)
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
