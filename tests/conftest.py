import os
import tempfile

os.environ.setdefault("CHRONOSPACE_DATA", tempfile.mkdtemp(prefix="chronospace-test-"))
os.environ.setdefault("CHRONOSPACE_SKIP_SEED", "1")
