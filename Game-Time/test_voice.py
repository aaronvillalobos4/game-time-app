import json
import os
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException
from voice import VoiceOffer, create_voice_session, session_config


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_key_returns_helpful_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(HTTPException) as raised:
                await create_voice_session(VoiceOffer(sdp="v=0\r\ns=voice"))
        self.assertEqual(raised.exception.status_code, 503)

    async def test_sdp_exchange_keeps_key_server_side(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch("voice.requests.post") as post:
            post.return_value = Mock(ok=True, text="v=0\r\ns=answer")
            response = await create_voice_session(VoiceOffer(sdp="v=0\r\ns=voice"))
            self.assertEqual(response.body, b"v=0\r\ns=answer")
            self.assertNotIn(b"test-secret", response.body)
            config = json.loads(post.call_args.kwargs["files"]["session"][1])
            self.assertFalse(config["audio"]["input"]["turn_detection"]["create_response"])
            self.assertTrue(config["audio"]["input"]["turn_detection"]["interrupt_response"])
            self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_provider_errors_do_not_expose_secrets(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch("voice.requests.post") as post:
            post.return_value = Mock(ok=False, text="private provider details")
            with self.assertRaises(HTTPException) as raised:
                await create_voice_session(VoiceOffer(sdp="v=0\r\ns=voice"))
            self.assertEqual(raised.exception.status_code, 502)
            self.assertNotIn("private", raised.exception.detail)

    async def test_network_failure_is_recoverable(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch("voice.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(HTTPException) as raised:
                await create_voice_session(VoiceOffer(sdp="v=0\r\ns=voice"))
            self.assertEqual(raised.exception.status_code, 502)

    def test_voice_can_be_configured_without_code_changes(self):
        with patch.dict(os.environ, {"OPENAI_REALTIME_VOICE": "cedar"}):
            self.assertEqual(session_config()["audio"]["output"]["voice"], "cedar")
