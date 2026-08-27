#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: F401,E402

from comment_deleter.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
