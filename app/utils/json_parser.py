from __future__ import annotations

import json
import re
from typing import Any

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def parse_json_safely(raw: str) -> Any:
    """Best-effort JSON extraction for model outputs."""
    text = (raw or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    match = _JSON_RE.search(text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None
