import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class BoundedPythonExecutor:
    def __init__(self):
        self.enabled = os.environ.get("EXECUTOR_ENABLED", "false").lower() == "true"
        self.timeout_seconds = int(os.environ.get("EXECUTOR_TIMEOUT_SECONDS", "90"))
        self.runner_path = Path(__file__).with_name("sandbox_runner.py")

    def run_python(self, code: str, data: object | None = None) -> str:
        if not self.enabled:
            return "The bounded Python executor is disabled in this environment."

        child_env = {
            "HOME": "/tmp",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHON_CODE_B64": base64.b64encode(code.encode()).decode(),
            "PYTHON_DATA_B64": base64.b64encode(json.dumps(data or []).encode()).decode(),
            "TMPDIR": "/tmp",
        }

        command = [
            "/usr/bin/prlimit",
            "--cpu=5",
            "--as=1073741824",
            "--nproc=16",
            "--fsize=65536",
            "--",
            "/usr/bin/setpriv",
            "--reuid=65532",
            "--regid=65532",
            "--clear-groups",
            "--no-new-privs",
            "--inh-caps=-all",
            "--ambient-caps=-all",
            "--bounding-set=-all",
            sys.executable,
            str(self.runner_path),
        ]

        with tempfile.TemporaryFile() as output:
            try:
                completed = subprocess.run(
                    command,
                    cwd="/tmp",
                    env=child_env,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return "The bounded Python execution exceeded its time limit."

            output.seek(0, os.SEEK_END)
            output.seek(max(0, output.tell() - 8000))
            result = output.read().decode(errors="replace").strip()

        if completed.returncode != 0:
            return "The bounded Python execution failed."
        return result or "Execution completed without a result."
