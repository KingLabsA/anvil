"""Test configuration: force offline keyword matching so the pattern matcher
never attempts a network model download during tests.
"""

import os

os.environ.setdefault("ERROR_RECOVERY_NO_EMBEDDINGS", "1")
