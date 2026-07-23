import subprocess
from unittest.mock import patch

from executor import BoundedPythonExecutor


def test_executor_runs_analysis_in_child_process(monkeypatch):
    monkeypatch.setenv("EXECUTOR_ENABLED", "true")
    executor = BoundedPythonExecutor()

    result = executor.run_python("sum(item['value'] for item in data)", [{"value": 2}, {"value": 3}])

    assert result == "5"


def test_executor_is_disabled_by_default():
    executor = BoundedPythonExecutor()

    assert executor.run_python("1 + 1") == "The bounded Python executor is disabled in this environment."


def test_executor_uses_limits_and_stripped_environment(monkeypatch):
    monkeypatch.setenv("EXECUTOR_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secret/credentials.json")
    executor = BoundedPythonExecutor()

    with patch("executor.subprocess.run") as run:
        run.return_value.returncode = 0
        executor.run_python("1 + 1")

    command = run.call_args.args[0]
    child_env = run.call_args.kwargs["env"]
    assert command[:2] == ["/usr/bin/prlimit", "--cpu=5"]
    assert "/usr/bin/setpriv" in command
    assert "--no-new-privs" in command
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in child_env
    assert set(child_env) == {
        "HOME",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "PYTHON_CODE_B64",
        "PYTHON_DATA_B64",
        "TMPDIR",
    }


def test_executor_enforces_wall_clock_timeout(monkeypatch):
    monkeypatch.setenv("EXECUTOR_ENABLED", "true")
    executor = BoundedPythonExecutor()

    with patch(
        "executor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="python", timeout=executor.timeout_seconds),
    ):
        result = executor.run_python("while True: pass")

    assert result == "The bounded Python execution exceeded its time limit."
