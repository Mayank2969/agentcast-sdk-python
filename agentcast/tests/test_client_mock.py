import pytest
import json
import httpx
from unittest.mock import MagicMock, patch
from agentcast.client import AgentCastClient
from agentcast.models import KeyPair

@pytest.fixture
def mock_keypair():
    return KeyPair(
        agent_id="test_agent_id",
        public_key_b64="test_pub_key",
        private_key_bytes=b"0" * 32
    )

@pytest.fixture
def client(mock_keypair):
    return AgentCastClient("http://api.test", mock_keypair)

def test_client_register_sends_correct_payload(client):
    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"agent_id": "registered_id"}
        mock_post.return_value = mock_resp
        
        result = client.register()
        
        assert result["agent_id"] == "registered_id"
        # Verify httpx.post was called with correct URL and JSON
        args, kwargs = mock_post.call_args
        assert args[0] == "http://api.test/v1/register"
        assert json.loads(kwargs["content"]) == {"public_key": "test_pub_key"}

def test_client_poll_handles_204(client):
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_get.return_value = mock_resp
        
        result = client.poll()
        assert result is None

def test_client_poll_returns_interview(client):
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "interview_id": "int_123",
            "question": "What is AI?",
            "github_repo_url": "https://github.com/test/repo"
        }
        mock_get.return_value = mock_resp
        
        interview = client.poll()
        assert interview.interview_id == "int_123"
        assert interview.question == "What is AI?"
        
        # Verify auth headers were present
        headers = mock_get.call_args[1]["headers"]
        assert "X-Agent-ID" in headers
        assert "X-Signature" in headers
        assert "X-Timestamp" in headers

def test_client_respond_sends_signed_payload(client):
    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        client.respond("int_123", "AI is great")
        
        args, kwargs = mock_post.call_args
        assert args[0] == "http://api.test/v1/interview/respond"
        body = json.loads(kwargs["content"])
        assert body["interview_id"] == "int_123"
        assert body["answer"] == "AI is great"
        
        # Verify X-Signature exists
        assert "X-Signature" in kwargs["headers"]

def test_client_abandon_uses_delete_method(client):
    with patch("httpx.delete") as mock_delete:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_delete.return_value = mock_resp
        
        client.abandon("int_123")
        
        args, kwargs = mock_delete.call_args
        assert args[0] == "http://api.test/v1/interview/int_123/abandon"
        assert "X-Signature" in kwargs["headers"]

def test_client_handles_http_errors(client):
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        # mock raise_for_status to actually raise
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_resp)
        mock_get.return_value = mock_resp
        
        with pytest.raises(httpx.HTTPStatusError):
            client.poll()
