import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.join(REPO_ROOT, "plugins", "comment-deleter")

sys.path.insert(0, os.path.join(PLUGIN_ROOT, "src"))
