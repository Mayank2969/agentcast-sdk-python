import json
import unittest
import uuid
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agentcast import AgentCastClient, KeyPair

class TestAgentCastClient(unittest.TestCase):
    def setUp(self):
        # Use real keys for signing logic to avoid mocking internal crypto methods
        self.priv = Ed25519PrivateKey.generate()
        
        self.keypair = MagicMock(spec=KeyPair)
        self.keypair.agent_id = "test_agent_id"
        self.keypair.private_key_bytes = b"dummy"
        self.keypair.public_key_b64 = "test_pub_b64"
        
        # Patch load_private_key to return our real private key
        with patch("agentcast.client.load_private_key", return_value=self.priv):
            self.client = AgentCastClient("http://localhost:8000", self.keypair)

    @patch("httpx.post")
    def test_get_dashboard_token(self, mock_post):
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "dashboard_token": "test_token",
            "expires_in": 3600,
            "agent_id": "test_agent_id"
        }
        mock_post.return_value = mock_resp
        
        token = self.client.get_dashboard_token()
        
        self.assertEqual(token, "test_token")
        mock_post.assert_called_once()
        # Verify path
        args, _ = mock_post.call_args
        self.assertIn("/v1/dashboard-token", args[0])

    @patch("httpx.get")
    def test_get_interview_history(self, mock_get):
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"sender": "HOST", "content": "Question 1", "sequence_num": 1, "timestamp": "2024-03-20T12:00:00"}
        ]
        mock_get.return_value = mock_resp
        
        interview_id = str(uuid.uuid4()) if 'uuid' in globals() else "test_id"
        history = self.client.get_interview_history(interview_id)
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "Question 1")
        mock_get.assert_called_once()
        args, _ = mock_get.call_args
        self.assertIn(interview_id, args[0])
        self.assertIn("/history", args[0])

if __name__ == "__main__":
    unittest.main()
