"""GIMP is the only renderer. Each job has private inputs, outputs and process state."""

import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .planner import validate_step


class EditorError(RuntimeError):
    pass


class GimpAdapter:
    def __init__(self, runtime: Path, executable=None, timeout=180):
        self.runtime = runtime
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.executable = executable or os.environ.get("LEMON_GIMP") or self.find()
        self.environment = None

    @staticmethod
    def find():
        for candidate in [
            shutil.which("gimp"),
            shutil.which("gimp-3.0"),
            "/Applications/GIMP.app/Contents/MacOS/gimp",
        ]:
            if candidate and Path(candidate).is_file():
                return str(candidate)
        return None

    def call(self, job):
        if not self.executable:
            raise EditorError("GIMP 3 is unavailable. Install GIMP and set LEMON_GIMP if it is not detected.")
        if job.get("step"):
            validate_step(job["step"])
        run_dir = self.runtime / uuid.uuid4().hex
        run_dir.mkdir(mode=0o700)
        job_file = run_dir / "job.json"
        job_file.write_text(json.dumps(job))
        worker = Path(__file__).with_name("gimp_worker.py")
        # Only this trusted, fixed worker is executed. User data is passed through JSON.
        command = [
            self.executable,
            "--new-instance",
            "--no-interface",
            "--no-data",
            "--no-fonts",
            "--no-shm",
            "--batch-interpreter=python-fu-eval",
            "--batch=" + "import runpy; runpy.run_path(" + repr(str(worker)) + ", run_name='__main__')",
            "--quit",
        ]
        env = {
            **{
                key: value
                for key, value in os.environ.items()
                if not any(part in key.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
            },
            "LEMON_JOB": str(job_file),
            "GIMP3_DIRECTORY": str(run_dir / "profile"),
            "XDG_CACHE_HOME": str(self.runtime / "cache"),
        }
        start = time.monotonic()
        with (run_dir / "process.log").open("wb") as log:
            try:
                proc = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
            except OSError:
                raise EditorError(
                    "GIMP could not start. Check the installation and LEMON_GIMP path."
                ) from None
            try:
                code = proc.wait(timeout=self.timeout)
            except BaseException:
                # Kill the complete private process group, including plug-ins, and reap it.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                raise EditorError(
                    "GIMP did not finish. Its private session was stopped; restore a saved version before continuing."
                ) from None
        result_file = run_dir / "result.json"
        if code or not result_file.exists():
            raise EditorError("GIMP failed without a verified result. Inspect the private runtime log.")
        data = json.loads(result_file.read_text())
        if not data["ok"]:
            raise EditorError(data["error"])
        result = data["result"]
        result["seconds"] = round(time.monotonic() - start, 3)
        self.environment = result.get("environment", result)
        return result

    def discover(self):
        return self.call({"action": "discover"})
