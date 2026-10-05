"""Mask restored/rotated Codex credentials before any CLI output reaches Actions."""
import json
from pathlib import Path
import sys


def mask_auth(path):
    try:
        auth = json.loads(Path(path).read_text(encoding="utf-8"))
        tokens = auth.get("tokens") or {}
        values = [auth.get("OPENAI_API_KEY"), *tokens.values()]
        for value in values:
            if isinstance(value, str) and value:
                escaped = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print(f"::add-mask::{escaped}")
        if not all(isinstance(tokens.get(key), str) and tokens[key]
                   for key in ("access_token", "refresh_token")):
            raise ValueError("missing subscription credentials")
    except (OSError, ValueError, AttributeError, TypeError):
        print("Invalid Codex auth file; upload subscription auth.json again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(mask_auth(sys.argv[1]))
