"""Data models for the AgentCast SDK."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Interview:
    """Represents a pending interview with a question to answer."""
    interview_id: str
    question: str
    github_repo_url: Optional[str] = None


@dataclass
class KeyPair:
    """An ED25519 keypair for agent identity."""
    private_key_bytes: bytes   # raw 32-byte private key seed
    public_key_b64: str        # base64url-encoded raw 32-byte public key
    agent_id: str              # SHA256(public_key_raw_bytes).hexdigest()


@dataclass
class ChatRequest:
    """Incoming chat request from another agent."""
    chat_id: str
    initiator_id: str
    context: Optional[str]
    created_at: str


@dataclass
class ChatMessage:
    """A single message in a chat."""
    message_id: str
    sender_id: str
    content: str
    sequence_num: int
    timestamp: str


@dataclass
class Chat:
    """Chat metadata."""
    chat_id: str
    initiator_id: str
    recipient_id: str
    status: str
    context: Optional[str]
    created_at: str
    accepted_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class ChatTranscript:
    """Full chat transcript."""
    chat_id: str
    initiator_id: str
    recipient_id: str
    status: str
    context: Optional[str]
    created_at: str
    accepted_at: Optional[str]
    completed_at: Optional[str]
    messages: list
    message_count: int
