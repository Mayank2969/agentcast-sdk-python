"""Unit tests for AgentCast Python SDK."""
import hashlib
import os
import stat
import time
from base64 import urlsafe_b64encode

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agentcast.crypto import generate_keypair, sign_request, save_keypair, load_keypair, load_private_key
from agentcast.models import Interview, KeyPair


def test_generate_keypair_creates_valid_keypair():
    kp = generate_keypair()
    assert len(kp.agent_id) == 64
    assert len(kp.public_key_b64) > 0
    assert len(kp.private_key_bytes) == 32


def test_agent_id_is_sha256_of_public_key():
    kp = generate_keypair()
    from base64 import urlsafe_b64decode
    raw = urlsafe_b64decode(kp.public_key_b64 + "==")
    expected_id = hashlib.sha256(raw).hexdigest()
    assert kp.agent_id == expected_id


def test_sign_request_produces_verifiable_headers():
    kp = generate_keypair()
    priv = load_private_key(kp.private_key_bytes)
    headers = sign_request(priv, kp.agent_id, "GET", "/v1/interview/next")
    assert "X-Agent-ID" in headers
    assert "X-Timestamp" in headers
    assert "X-Signature" in headers
    assert headers["X-Agent-ID"] == kp.agent_id
    assert abs(int(headers["X-Timestamp"]) - time.time()) < 5


def test_sign_request_timestamp_freshness():
    kp = generate_keypair()
    priv = load_private_key(kp.private_key_bytes)
    headers = sign_request(priv, kp.agent_id, "POST", "/v1/interview/respond", b'{"answer":"test"}')
    ts = int(headers["X-Timestamp"])
    assert abs(ts - time.time()) < 5


def test_save_and_load_keypair(tmp_path):
    kp = generate_keypair()
    key_file = str(tmp_path / "agent.key")
    save_keypair(kp, key_file)
    loaded = load_keypair(key_file)
    assert loaded.agent_id == kp.agent_id
    assert loaded.public_key_b64 == kp.public_key_b64
    assert loaded.private_key_bytes == kp.private_key_bytes


def test_two_keypairs_produce_different_agent_ids():
    kp1 = generate_keypair()
    kp2 = generate_keypair()
    assert kp1.agent_id != kp2.agent_id


def test_save_keypair_sets_secure_permissions(tmp_path):
    """Verify that save_keypair() creates files with secure permissions (0o600)."""
    kp = generate_keypair()
    key_file = str(tmp_path / "agent.key")
    save_keypair(kp, key_file)

    # Check that file exists
    assert os.path.exists(key_file)

    # Check file permissions are 0o600 (owner read/write only)
    file_stat = os.stat(key_file)
    file_mode = stat.S_IMODE(file_stat.st_mode)
    assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

    # Verify it's readable by owner and not by group/others
    assert file_stat.st_mode & stat.S_IRUSR  # owner can read
    assert file_stat.st_mode & stat.S_IWUSR  # owner can write
    assert not (file_stat.st_mode & stat.S_IRGRP)  # group cannot read
    assert not (file_stat.st_mode & stat.S_IROTH)  # others cannot read
