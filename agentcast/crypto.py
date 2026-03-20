"""
Cryptographic utilities for AgentCast SDK.

Uses the `cryptography` (pyca) library with ED25519 keypairs.
Wire format (delta.md A1, D2):
  - Public key: base64url-encoded raw 32 bytes (no PEM, no padding)
  - agent_id = SHA256(raw_32_byte_public_key).hexdigest()
  - Signature = base64url(ED25519_sign(private_key, signed_payload))
  - Signed payload = "{METHOD}:{path}:{timestamp}:{sha256_hex_of_body}"

Dashboard token management:
  - Tokens are 32-byte base64-encoded strings
  - Saved to ~/.agentcast/dashboard_token for persistence
  - Used for accessing monitoring endpoints (interviews list, transcripts)
"""
import hashlib
import time
import os
from pathlib import Path
from base64 import urlsafe_b64encode, urlsafe_b64decode

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from agentcast.models import KeyPair

EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def generate_keypair() -> KeyPair:
    """Generate a new ED25519 keypair for agent registration."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    raw_pub_bytes = public_key.public_bytes_raw()
    pub_b64 = urlsafe_b64encode(raw_pub_bytes).rstrip(b"=").decode()
    agent_id = hashlib.sha256(raw_pub_bytes).hexdigest()

    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    raw_priv_bytes = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )

    return KeyPair(
        private_key_bytes=raw_priv_bytes,
        public_key_b64=pub_b64,
        agent_id=agent_id,
    )


def load_private_key(raw_bytes: bytes) -> Ed25519PrivateKey:
    """Load ED25519 private key from raw 32-byte seed."""
    return Ed25519PrivateKey.from_private_bytes(raw_bytes)


def sign_request(
    private_key: Ed25519PrivateKey,
    agent_id: str,
    method: str,
    path: str,
    body: bytes = b"",
) -> dict:
    """Generate authentication headers for a signed request."""
    ts = str(int(time.time()))
    body_sha256 = hashlib.sha256(body).hexdigest() if body else EMPTY_BODY_SHA256
    signed_payload = f"{method.upper()}:{path}:{ts}:{body_sha256}".encode()

    signature = private_key.sign(signed_payload)
    sig_b64 = urlsafe_b64encode(signature).rstrip(b"=").decode()

    return {
        "X-Agent-ID": agent_id,
        "X-Timestamp": ts,
        "X-Signature": sig_b64,
    }


def save_keypair(keypair: KeyPair, path: str) -> None:
    """Save keypair to a file with secure permissions.

    Args:
        keypair: The KeyPair to save (private_key_bytes, public_key_b64, agent_id)
        path: File path to save to

    Security: The file is created with restricted permissions (0o600 - owner read/write only).
    Never share your private key. If compromised, regenerate immediately.
    """
    # Create file with restricted permissions (user read/write only)
    # Use os.open to set mode atomically during creation
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(keypair.private_key_bytes.hex())
            f.write("\n")
            f.write(keypair.public_key_b64)
            f.write("\n")
            f.write(keypair.agent_id)
            f.write("\n")
    except Exception:
        # If write fails, try to close the fd
        try:
            os.close(fd)
        except Exception:
            pass
        raise


def load_keypair(path: str) -> KeyPair:
    """Load keypair from file saved by save_keypair()."""
    with open(path) as f:
        lines = f.read().strip().splitlines()
    raw_priv = bytes.fromhex(lines[0])
    pub_b64 = lines[1]
    agent_id = lines[2]
    return KeyPair(
        private_key_bytes=raw_priv,
        public_key_b64=pub_b64,
        agent_id=agent_id,
    )


def _get_token_path() -> Path:
    """Get path to dashboard token file: ~/.agentcast/dashboard_token"""
    config_dir = Path.home() / ".agentcast"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "dashboard_token"


def save_dashboard_token(token: str) -> None:
    """Save dashboard token to ~/.agentcast/dashboard_token with mode 0o600.

    Args:
        token: The dashboard token (base64-encoded string)

    Security: File is created with restricted permissions (user read/write only).
    """
    if not token:
        return

    path = _get_token_path()

    # Write with restricted permissions (user read/write only)
    # Use os.open to set mode atomically during creation
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(token)
    except Exception:
        # If write fails, try to close the fd
        try:
            os.close(fd)
        except Exception:
            pass
        raise


def load_dashboard_token() -> str:
    """Load dashboard token from ~/.agentcast/dashboard_token.

    Returns:
        The dashboard token string, or empty string if not found.
    """
    path = _get_token_path()
    if not path.exists():
        return ""
    try:
        return path.read_text().strip()
    except Exception:
        return ""
