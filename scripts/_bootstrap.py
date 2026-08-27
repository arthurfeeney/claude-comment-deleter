import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
_SOURCE_ROOT = os.path.join(_PLUGIN_ROOT, "src")
if _SOURCE_ROOT not in sys.path:
    sys.path.insert(0, _SOURCE_ROOT)


def read_event():
    import json

    try:
        return json.load(sys.stdin)
    except (ValueError, OSError):
        return {}
