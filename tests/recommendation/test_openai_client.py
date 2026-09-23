"""Offline transport tests: all network operations are mocked at urllib."""

from copy import deepcopy
import http.client
import io
import json
import socket
import traceback
import unittest
from unittest.mock import MagicMock, patch
from urllib import error, request

from backend.ai.openai_client import (
    MAX_RESPONSE_BYTES, RESPONSES_URL, OpenAITransportError, _NoRedirect,
    extract_output_text, request_json,
)


FAKE_KEY = "fake-test-key-only"


def envelope(text='{"explanation":"Useful activity"}'):
    return {
        "id": "resp_fake", "object": "response", "status": "completed",
        "error": None, "incomplete_details": None,
        "output": [{
            "id": "msg_fake", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
    }


class ResponsesTransportTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch("backend.ai.openai_client.request.build_opener")
        self.build_opener = self.patch.start()
        self.addCleanup(self.patch.stop)
        self.opener = self.build_opener.return_value
        self.response = MagicMock()
        self.response.__enter__.return_value = self.response
        self.response.getcode.return_value = 200
        self.response.read.return_value = json.dumps(envelope()).encode("utf-8")
        self.opener.open.return_value = self.response
        self.payload = {"model": "gpt-4.1-mini", "store": False, "tools": [], "input": "Оқу"}

    def call(self, **changes):
        return request_json(self.payload, api_key=changes.get("api_key", FAKE_KEY),
                            timeout_seconds=changes.get("timeout_seconds", 2.5))

    def assert_error(self, code, **changes):
        with self.assertRaises(OpenAITransportError) as raised:
            self.call(**changes)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)
        self.assertNotIn(FAKE_KEY, repr(raised.exception))
        return raised.exception

    def test_posts_once_to_fixed_endpoint_with_json_auth_and_timeout(self):
        before = deepcopy(self.payload)
        result = self.call()
        self.assertEqual(result, envelope())
        self.build_opener.assert_called_once()
        self.assertIsInstance(self.build_opener.call_args.args[0], _NoRedirect)
        self.opener.open.assert_called_once()
        req = self.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + FAKE_KEY)
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(req.get_header("Accept"), "application/json")
        self.assertEqual(json.loads(req.data), self.payload)
        self.assertEqual(self.opener.open.call_args.kwargs, {"timeout": 2.5})
        self.response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
        self.response.__exit__.assert_called_once()
        self.assertEqual(self.payload, before)

    def test_payload_cannot_change_transport_destination(self):
        self.payload["url"] = "https://untrusted.invalid/collect"
        self.call()
        self.assertEqual(self.opener.open.call_args.args[0].full_url, RESPONSES_URL)

    def test_redirect_handler_never_forwards_authorization(self):
        handler = _NoRedirect()
        handler.parent = MagicMock()
        req = request.Request(RESPONSES_URL, data=b"{}", headers={"Authorization": "Bearer " + FAKE_KEY})
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertIsNone(handler.redirect_request(req, None, code, "Redirect", {}, "https://untrusted.invalid"))
        # The redirect handler declines the redirect. urllib's default error
        # handler then raises HTTPError; no redirected open is attempted.
        self.assertIsNone(handler.http_error_302(
            req, io.BytesIO(b"body must not be read"), 302, "Redirect",
            {"location": "https://untrusted.invalid"},
        ))
        handler.parent.open.assert_not_called()

    def test_socket_and_url_wrapped_timeouts_map_to_timeout_without_retry(self):
        for cause in (socket.timeout("private detail"), TimeoutError("private detail"),
                      error.URLError(socket.timeout("private detail"))):
            with self.subTest(cause=type(cause).__name__):
                self.opener.open.reset_mock()
                self.opener.open.side_effect = cause
                self.assert_error("timeout")
                self.opener.open.assert_called_once()

    def test_read_timeout_is_sanitized_and_response_closes(self):
        self.response.read.side_effect = socket.timeout(FAKE_KEY)
        self.assert_error("timeout")
        self.response.__exit__.assert_called_once()

    def test_http_errors_close_without_reading_error_body_or_retrying(self):
        for status in (301, 401, 403, 429, 500):
            with self.subTest(status=status):
                self.opener.open.reset_mock()
                body = MagicMock()
                failure = error.HTTPError(RESPONSES_URL, status, FAKE_KEY, {}, body)
                self.opener.open.side_effect = failure
                caught = self.assert_error("api_error")
                body.read.assert_not_called()
                body.close.assert_called_once()
                self.opener.open.assert_called_once()
                self.assertTrue(caught.__suppress_context__)

    def test_error_traceback_never_includes_reflected_secret_or_response_body(self):
        self.opener.open.side_effect = error.URLError("reflected-private-value-9751")
        try:
            self.call()
        except OpenAITransportError:
            formatted = traceback.format_exc()
        self.assertNotIn("reflected-private-value-9751", formatted)
        self.assertNotIn(FAKE_KEY, formatted)

    def test_network_and_http_protocol_errors_map_to_api_error(self):
        for cause in (error.URLError("DNS failure"), OSError("private network data"),
                      http.client.RemoteDisconnected("private connection data")):
            with self.subTest(cause=type(cause).__name__):
                self.opener.open.side_effect = cause
                self.assert_error("api_error")

    def test_non_200_status_is_rejected_without_reading_body(self):
        self.response.getcode.return_value = 503
        self.assert_error("api_error")
        self.response.read.assert_not_called()

    def test_response_size_is_bounded_and_exact_limit_remains_valid(self):
        self.response.read.return_value = b"{" + b" " * MAX_RESPONSE_BYTES
        self.assert_error("invalid_response")
        self.response.read.reset_mock()
        self.response.read.return_value = b"{}" + b" " * (MAX_RESPONSE_BYTES - 2)
        self.assertEqual(self.call(), {})
        self.response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)

    def test_invalid_utf8_json_shapes_duplicates_and_nonfinite_numbers_are_rejected(self):
        malformed = (
            b"\xff", b"not-json", b"[]", b"null", b'"text"',
            b'{"status":"completed","status":"failed"}', b'{"x":{"a":1,"a":2}}',
            b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                self.response.read.return_value = raw
                self.assert_error("invalid_response")

    def test_invalid_outgoing_json_never_reaches_network(self):
        for payload in ([], {"value": float("nan")}, {"value": object()}):
            with self.subTest(payload=type(payload).__name__):
                self.payload = payload
                self.assert_error("invalid_response")
                self.build_opener.assert_not_called()

    def test_missing_or_invalid_credentials_never_reach_network(self):
        for key in (None, "", " ", "a\nb", "a\rb", "a\tb", "a\x00b", "a\x7fb", "тест"):
            with self.subTest(key=repr(key)):
                self.assert_error("api_error", api_key=key)
                self.build_opener.assert_not_called()

    def test_invalid_timeout_never_reaches_network(self):
        for value in (0, -1, True, None, "2", float("inf"), float("nan")):
            with self.subTest(timeout=repr(value)):
                self.assert_error("api_error", timeout_seconds=value)
                self.build_opener.assert_not_called()


class ResponseEnvelopeTests(unittest.TestCase):
    def test_one_completed_assistant_text_is_returned_without_rewriting(self):
        text = ' {"explanation":"Полезный курс"}\n'
        value = envelope(text)
        before = deepcopy(value)
        self.assertEqual(extract_output_text(value), text)
        self.assertEqual(value, before)

    def test_incomplete_failed_or_error_envelopes_are_not_used(self):
        for changes in ({"status": "incomplete"}, {"status": "failed"}, {"status": "in_progress"},
                        {"status": None}, {"error": {}}, {"error": {"message": "private"}},
                        {"incomplete_details": {"reason": "max_output_tokens"}}):
            with self.subTest(changes=changes):
                value = envelope()
                value.update(changes)
                with self.assertRaises(OpenAITransportError) as raised:
                    extract_output_text(value)
                self.assertEqual(raised.exception.code, "invalid_response")

    def test_sdk_convenience_output_text_without_rest_output_is_rejected(self):
        with self.assertRaises(OpenAITransportError):
            extract_output_text({"status": "completed", "output_text": "text"})

    def test_refusals_tool_calls_reasoning_and_unknown_blocks_are_rejected(self):
        for item in (
            {"type": "function_call", "name": "tool", "arguments": "{}"},
            {"type": "reasoning", "summary": []},
            {"type": "unknown"},
        ):
            with self.subTest(type=item["type"]):
                value = envelope()
                value["output"] = [item]
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)
        for content_type in ("refusal", "output_audio", "unknown"):
            with self.subTest(content_type=content_type):
                value = envelope()
                value["output"][0]["content"] = [{"type": content_type, "text": "text", "refusal": "No"}]
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)

    def test_multiple_messages_or_text_blocks_are_rejected(self):
        for multiple_messages in (True, False):
            with self.subTest(multiple_messages=multiple_messages):
                value = envelope()
                if multiple_messages:
                    value["output"].append(deepcopy(value["output"][0]))
                else:
                    value["output"][0]["content"].append({"type": "output_text", "text": "another"})
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)

    def test_partial_or_nonassistant_messages_are_rejected(self):
        for field, invalid in (("role", "user"), ("role", "system"), ("status", "in_progress"), ("status", None)):
            with self.subTest(field=field, value=invalid):
                value = envelope()
                value["output"][0][field] = invalid
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)

    def test_missing_malformed_empty_output_or_text_is_rejected(self):
        for output in (None, [], {}, [None], ["message"]):
            with self.subTest(output=output):
                value = envelope()
                value["output"] = output
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)
        for content in (None, [], {}, [None], [{"type": "output_text", "text": ""}],
                        [{"type": "output_text", "text": "  "}], [{"type": "output_text", "text": 123}]):
            with self.subTest(content=content):
                value = envelope()
                value["output"][0]["content"] = content
                with self.assertRaises(OpenAITransportError):
                    extract_output_text(value)
        for value in (None, [], "response", 123):
            with self.subTest(value=value), self.assertRaises(OpenAITransportError):
                extract_output_text(value)


if __name__ == "__main__":
    unittest.main()
