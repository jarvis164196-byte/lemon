"""Local RAW development boundary; subsequent editing and rendering belongs to GIMP."""

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from .imaging import validate_image

RAW_EXTENSIONS = frozenset(
    ".cr2 .cr3 .crw .nef .nrw .arw .srf .sr2 .raf .dng .orf .rw2 .raw .pef .srw .3fr .fff .iiq .kdc .dcr .erf .mos .mrw .mef".split()
)
MAX_UPLOAD_BYTES = 128 * 1024 * 1024


def develop(source: Path, directory: Path, timeout=120):
    """Work only on a private copy, without loading user sidecars or editor presets."""
    if source.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError("RAW files must be smaller than 128 MB.")
    directory.mkdir(mode=0o700)
    copied = directory / ("input" + source.suffix.lower())
    shutil.copyfile(source, copied)
    output = directory / "developed.png"
    job = {"input": str(copied), "output": str(output), "status": "prepared"}
    (directory / "job.json").write_text(json.dumps(job))
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    env["OMP_NUM_THREADS"] = "2"
    with (directory / "process.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "lemon.raw_worker", str(directory / "job.json")],
            stdout=log,
            stderr=log,
            env=env,
            start_new_session=True,
        )
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise ValueError("RAW conversion did not finish. Its private process was stopped.") from None
    result = directory / "result.json"
    if code or not result.is_file():
        raise ValueError(
            "RAW conversion failed. This file or camera may be unsupported by the installed decoder."
        )
    evidence = json.loads(result.read_text())
    if not evidence["ok"]:
        raise ValueError(evidence["error"])
    validate_image(output, max_bytes=256 * 1024 * 1024)
    return output, evidence["conversion"]
