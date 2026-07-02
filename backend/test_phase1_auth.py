import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

from app.auth.auth import verify_google_token, create_jwt_token, verify_jwt_token

class TestAuthAndLogging(unittest.TestCase):
    def setUp(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "753938336938-3dp41nocsvj3qlabh87j25j15k4r7enr.apps.googleusercontent.com")

    def test_create_and_verify_jwt(self):
        user_info = {
            "sub": "12345",
            "name": "Test User",
            "email": "test@nobroker.in",
            "picture": "http://avatar.jpg"
        }
        session_id = "test-session-uuid"
        token = create_jwt_token(user_info, session_id)
        
        # Verify decoding
        payload = verify_jwt_token(token)
        self.assertEqual(payload["sub"], "12345")
        self.assertEqual(payload["email"], "test@nobroker.in")
        self.assertEqual(payload["session_id"], session_id)
        
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_verify_google_token_nobroker(self, mock_verify):
        mock_verify.return_value = {
            "aud": self.client_id,
            "iss": "accounts.google.com",
            "email": "employee@nobroker.in",
            "name": "NoBroker Employee",
            "picture": "http://pic.jpg",
            "sub": "google-id-1"
        }
        res = verify_google_token("valid-nobroker-token")
        self.assertEqual(res["email"], "employee@nobroker.in")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_verify_google_token_gmail_rejected(self, mock_verify):
        mock_verify.return_value = {
            "aud": self.client_id,
            "iss": "accounts.google.com",
            "email": "someone@gmail.com",
            "name": "Gmail User",
            "picture": "http://pic.jpg",
            "sub": "google-id-2"
        }
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            verify_google_token("gmail-token")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Only NoBroker employees can access FinSight AI", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
