import atexit
import os
import shutil
import tempfile

_test_dir = tempfile.mkdtemp(prefix="awaaz-test-")
os.environ["AWAAZ_DATA_DIR"] = _test_dir
os.environ["AWAAZ_DATABASE_URL"] = "sqlite+aiosqlite://"
atexit.register(shutil.rmtree, _test_dir, ignore_errors=True)
