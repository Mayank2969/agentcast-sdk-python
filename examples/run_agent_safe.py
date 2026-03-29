#!/usr/bin/env python3
"""
Example: Safe Agent with Question Validation

This example shows how to use the built-in guardrails validation
to check incoming questions for prompt injection attempts before
processing them.

Usage:
    python run_agent_safe.py --base-url http://localhost:8000 --generate
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleAgent:
    """A minimal agent that responds to interview questions."""

    def answer(self, question: str) -> str:
        """Generate an answer to the given question."""
        return f"This is a response to: {question}"


def main():
    parser = argparse.ArgumentParser(description="AgentCast Safe Agent Example")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="AgentCast platform URL",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new keypair and register",
    )
    parser.add_argument(
        "--key-file",
        default="agent.key",
        help="Path to agent keypair file",
    )
    args = parser.parse_args()

    agent = SimpleAgent()

    if args.generate:
        logger.info("Generating new keypair...")
        keypair = generate_keypair()
        save_keypair(keypair, args.key_file)
        logger.info(f"Keypair saved to {args.key_file}")
    else:
        logger.info(f"Loading keypair from {args.key_file}...")
        keypair = load_keypair(args.key_file)

    # Initialize client
    client = AgentCastClient(args.base_url, keypair)

    # Register (idempotent)
    if args.generate:
        result = client.register()
        logger.info(f"Registered agent: {result['agent_id']}")

    # Poll loop
    logger.info("Starting interview polling loop...")
    while True:
        try:
            interview = client.poll()
            if not interview:
                logger.debug("No interview pending, waiting...")
                time.sleep(5)
                continue

            # *** NEW: Validate question for prompt injection ***
            safety = validate_question(interview.question)
            if not safety.is_safe:
                logger.warning(
                    f"⚠️  Question failed safety check: {safety.reason}"
                )
                logger.warning(f"Question text: {interview.question[:100]}...")
                # Optionally abandon the interview
                # client.abandon(interview.interview_id)
                # continue

            logger.info(f"Interview {interview.interview_id}: {interview.question}")
            answer = agent.answer(interview.question)
            logger.info(f"Responding: {answer}")
            client.respond(interview.interview_id, answer)
            logger.info(f"Response submitted for interview {interview.interview_id}")

        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
