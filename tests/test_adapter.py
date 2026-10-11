import sys
import time

import pytest

from lemon.gimp import EditorError, GimpAdapter


def test_timeout_stops_private_process_without_retry(tmp_path):
    executable = tmp_path / "slow-editor"
    executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    executable.chmod(0o700)
    adapter = GimpAdapter(tmp_path / "runtime", str(executable), timeout=0.1)
    start = time.monotonic()
    with pytest.raises(EditorError, match="private session was stopped"):
        adapter.discover()
    assert time.monotonic() - start < 5
    assert len(list((tmp_path / "runtime").glob("*/job.json"))) == 1
