"""Small, bounded Responses API HTTPS transport with no SDK dependency.

No credential lookup, retries, logging, or model decisions happen here. The
caller owns the overall deadline; urllib's timeout bounds network operations.
Only the fixed OpenAI endpoint is used and HTTP redirects are disabled.
"""

from collections.abc import Mapping
import http.client
import json
from math import isfinite
import socket
from urllib import error, request


RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_RESPONSE_BYTES = 256 * 1024


class OpenAITransportError(Exception):
    """Safe fallback reason, without API body, credentials, or exception detail."""

    def __init__(self, code):
        self.code = code if code in ("timeout", "api_error", "invalid_response") else "invalid_response"
        super().__init__(self.code)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Returning None causes urllib to raise HTTPError without issuing a
        # redirected request or forwarding the Authorization header.
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite JSON value")


def _finite_float(value):
    number = float(value)
    if not isfinite(number):
        raise ValueError("Nonfinite JSON number")
    return number


def _parse_envelope(raw):
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=_reject_constant, parse_float=_finite_float)
    except (ValueError, UnicodeError, RecursionError):
        raise OpenAITransportError("invalid_response") from None
    if not isinstance(parsed, dict):
        raise OpenAITransportError("invalid_response")
    return parsed


def request_json(payload: Mapping, *, api_key: str, timeout_seconds: float) -> dict:
    """POST once and return the raw REST envelope, or a sanitized exception."""
    if (not isinstance(api_key, str) or not api_key
            or not api_key.isascii() or any(character.isspace() or ord(character) < 33
                                           or ord(character) == 127 for character in api_key)):
        raise OpenAITransportError("api_error")
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise OpenAITransportError("api_error")
    if not isinstance(payload, Mapping):
        raise OpenAITransportError("invalid_response")
    try:
        body = json.dumps(dict(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        raise OpenAITransportError("invalid_response") from None
    req = request.Request(
        RESPONSES_URL, data=body, method="POST",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        opener = request.build_opener(_NoRedirect())
        with opener.open(req, timeout=timeout_seconds) as response:
            if response.getcode() != 200:
                raise OpenAITransportError("api_error")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
                raise OpenAITransportError("invalid_response")
    except error.HTTPError as exc:
        # Never read error bodies: they may contain reflected request data.
        try:
            exc.close()
        finally:
            raise OpenAITransportError("api_error") from None
    except (socket.timeout, TimeoutError):
        raise OpenAITransportError("timeout") from None
    except error.URLError as exc:
        code = "timeout" if isinstance(exc.reason, (socket.timeout, TimeoutError)) else "api_error"
        raise OpenAITransportError(code) from None
    except (OSError, http.client.HTTPException, ValueError, OverflowError):
        raise OpenAITransportError("api_error") from None
    return _parse_envelope(raw)


def extract_output_text(response) -> str:
    """Accept one completed assistant text, rejecting refusals and tool output.

    ``output_text`` is an SDK convenience property, not the REST envelope shape.
    Reasoning/tool/audio items and partial outputs are intentionally unsupported
    by this small explanation adapter and trigger deterministic fallback.
    """
    if (not isinstance(response, Mapping) or response.get("status") != "completed"
            or response.get("error") is not None or response.get("incomplete_details") is not None):
        raise OpenAITransportError("invalid_response")
    output = response.get("output")
    if not isinstance(output, list) or len(output) != 1:
        raise OpenAITransportError("invalid_response")
    message = output[0]
    if (not isinstance(message, Mapping) or message.get("type") != "message"
            or message.get("role") != "assistant" or message.get("status") != "completed"):
        raise OpenAITransportError("invalid_response")
    content = message.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise OpenAITransportError("invalid_response")
    block = content[0]
    if (not isinstance(block, Mapping) or block.get("type") != "output_text"
            or not isinstance(block.get("text"), str) or not block["text"].strip()):
        raise OpenAITransportError("invalid_response")
    return block["text"]
