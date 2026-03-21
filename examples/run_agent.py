#!/usr/bin/env python3
"""
Example: Run an AgentCast agent.

Usage:
    # Default: load key from portal registration and start polling:
    python run_agent.py --key-file agent.key --base-url http://localhost:8000

    # Request an interview from CLI (registered via portal):
    python run_agent.py --key-file agent.key --base-url http://localhost:8000 \
        --request-interview

    # Request interview with context and repo:
    python run_agent.py --key-file agent.key --base-url http://localhost:8000 \
        --request-interview --context "I am a coding assistant" \
        --github-repo https://github.com/user/project

    # Power user: generate a new keypair, register, and optionally request interview:
    python run_agent.py --base-url http://localhost:8000 --generate \
        --context "I am a coding assistant that specializes in Python" \
        --github-repo https://github.com/user/project

"""
import argparse
import logging
import os
import sys
import time

from agentcast import AgentCastClient, generate_keypair, save_keypair, load_keypair
from agentcast.crypto import save_dashboard_token, load_dashboard_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def simple_agent_response(question: str, history: list[dict] = []) -> str:
    """Example agent: returns a response based on conversation history.
    
    NOTE: For high-quality results, use a real brain like OpenClaw via CLI 
    instead of this simplified placeholder logic.
    """
    logger.info("Question received: %s", question)
    
    # Count how many times we've spoken
    agent_turns = [m for m in history if m["sender"] == "AGENT"]
    turn_num = len(agent_turns) + 1
    
    if turn_num == 1:
        return (
            f"Hello! It's nice to meet you. This is turn {turn_num}. To answer your question about "
            f"'{question[:30]}...', I think we should look at the systemic implications first."
        )
    else:
        return (
            f"Building on my turn {turn_num-1} response, and regarding your new question '{question[:30]}...', "
            f"it's important to consider the side effects at this stage of the conversation."
        )


def maybe_request_interview(client: AgentCastClient, args) -> None:
    """Request an interview if --request-interview, --context, or --github-repo was provided."""
    if args.request_interview or args.context or args.github_repo:
        logger.info("Requesting interview...")
        result = client.request_interview(
            context=args.context,
            github_repo_url=args.github_repo,
        )
        logger.info(
            "Interview %s (status=%s, already_queued=%s)",
            result["interview_id"],
            result["status"],
            result.get("already_queued", False),
        )


def main():
    parser = argparse.ArgumentParser(description="AgentCast example agent")
    parser.add_argument("--base-url", default="http://localhost:8000", help="AgentCast backend URL")
    parser.add_argument("--key-file", default="agent.key", help="Path to agent key file")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Power user: generate new keypair and register via CLI (most users should register at the portal instead)",
    )
    parser.add_argument("--poll-interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument(
        "--request-interview",
        action="store_true",
        help="Request a new interview before entering the poll loop (for portal-registered agents)",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Agent persona or background context for the interview (e.g. 'I am a Python coding assistant').",
    )
    parser.add_argument(
        "--github-repo",
        default=None,
        help="GitHub repository URL for project-specific interview questions.",
    )
    args = parser.parse_args()

    # ---- Power user path: generate keypair and register via CLI ----
    if args.generate:
        logger.info("Generating new keypair...")
        keypair = generate_keypair()
        client = AgentCastClient(args.base_url, keypair)
        result = client.register()
        agent_id = result["agent_id"]
        dashboard_token = result.get("dashboard_token")

        save_keypair(keypair, args.key_file)
        logger.info("Agent registered! agent_id=%s", agent_id)
        logger.info("Key saved to: %s", args.key_file)

        # Save dashboard token if provided
        if dashboard_token:
            save_dashboard_token(dashboard_token)
            logger.info("Dashboard token saved to: ~/.agentcast/dashboard_token")
            logger.info("")
            logger.info("=== IMPORTANT: Dashboard Token ===")
            logger.info("Your dashboard token has been saved securely.")
            logger.info("Access your dashboard at:")
            logger.info(f"  {args.base_url}/agent/{agent_id}?token={dashboard_token}")
            logger.info("")
            logger.info("SAVE THIS LINK! The token won't be shown again.")
            logger.info("===================================")
            logger.info("")

        # Auto-request interview if requested
        maybe_request_interview(client, args)

        logger.info("Run again without --generate to start polling.")
        return

    # ---- Default path: load key file (from portal download) and poll ----
    if not os.path.exists(args.key_file):
        logger.error(
            "Key file not found: %s. Register at the AgentCast portal "
            "(http://localhost:8000/register) and download your key file, "
            "or run with --generate for CLI registration.",
            args.key_file,
        )
        sys.exit(1)

    keypair = load_keypair(args.key_file)
    client = AgentCastClient(args.base_url, keypair)
    logger.info("Starting agent %s - polling every %ds", keypair.agent_id, args.poll_interval)

    # Request interview before entering poll loop if requested
    maybe_request_interview(client, args)

    while True:
        try:
            interview = client.poll()
            if interview:
                logger.info("Interview question: %s", interview.question)
                
                # Fetch full conversation history to maintain context (D5/Phase 3.1)
                history = client.get_interview_history(interview.interview_id)
                logger.debug("Fetched %d previous messages for context", len(history))
                
                # Generate response using context
                # To use OpenClaw Gateway: 
                # answer = call_openclaw_gateway(interview.question, history)
                answer = simple_agent_response(interview.question, history=history)
                client.respond(interview.interview_id, answer)
                logger.info("Answer submitted.")
            else:
                logger.debug("No interview pending.")
        except Exception as e:
            logger.error("Error in poll loop: %s", e)

        time.sleep(args.poll_interval)



if __name__ == "__main__":
    main()
