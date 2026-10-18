"""Shared redaction helpers for runtime capture adapters.

The SDK's ``PayloadRedactor`` is a shallow pass over top-level keys. Adapters
receive nested runtime payloads (tool args, messages, metadata), so they need
a deep pass that (a) redacts sensitive keys at every depth, (b) redacts string
values that look like credentials, and (c) additionally runs every nested
dict through the configured ``PayloadRedactor``.
"""

from __future__ import annotations

import re
from typing import Any

from sdk.privacy import PayloadRedactor

# Regex patterns detecting sensitive keys and secret values. A key is
# sensitive when its last separator-delimited segment is one of the sensitive
# words (optionally plural/possessive), so "access_token" and "client_secret"
# match while usage counters like "token_usage" or "total_tokens_used" do not.
_SECRET_KEY_RE = re.compile(
    r"^(?:.*[_-])?(?:api[_-]?key|authorization|bearer|token|secret|password)s?$", re.I
)
_SECRET_VALUE_RE = re.compile(r"(?:bearer\s+|sk[-_]|api[_-]?key\s*[=:])", re.I)


# Recursively sanitize nested dictionaries and lists before persistence
def redact_value(value: Any, redactor: PayloadRedactor) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, nested in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = redact_value(nested, redactor)
        return redactor.redact(safe)
    if isinstance(value, list):
        return [redact_value(item, redactor) for item in value]
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        return "[REDACTED]"
    return value
