import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path


class DemoScenarioAuthorizationError(Exception):
    pass


class DemoScenarioRateLimitError(Exception):
    pass


class DemoScenarioUnavailableError(Exception):
    pass


class DemoScenarioService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_success = 0.0
        self._run_day = None
        self._run_count = 0

    async def maybe_run(
        self,
        message: str,
        history: list[dict],
        operator_token: str | None,
    ) -> dict | None:
        prompt_digest = os.environ.get("DEMO_SCENARIO_3_PROMPT_SHA256", "")
        if history or not prompt_digest or not self._matches_digest(message, prompt_digest):
            return None

        if os.environ.get("DEMO_SCENARIOS_ENABLED", "false").lower() != "true":
            raise DemoScenarioUnavailableError("Demo scenarios are disabled.")

        token_digest = os.environ.get("DEMO_SCENARIO_3_TOKEN_SHA256", "")
        if not operator_token or not token_digest or not self._matches_digest(
            operator_token, token_digest
        ):
            raise DemoScenarioAuthorizationError("Demo operator token required.")

        async with self._lock:
            self._enforce_run_limits()
            result = await asyncio.to_thread(self._execute)
            self._record_success()
            return result

    @staticmethod
    def _matches_digest(value: str, expected: str) -> bool:
        actual = hashlib.sha256(value.encode()).hexdigest()
        return hmac.compare_digest(actual, expected)

    def _enforce_run_limits(self):
        now = time.monotonic()
        cooldown = int(os.environ.get("DEMO_SCENARIO_COOLDOWN_SECONDS", "1800"))
        if self._last_success and now - self._last_success < cooldown:
            raise DemoScenarioRateLimitError("Demo scenario cooldown is active.")

        today = datetime.now(UTC).date()
        if self._run_day != today:
            self._run_day = today
            self._run_count = 0
        daily_limit = int(os.environ.get("DEMO_SCENARIO_DAILY_LIMIT", "6"))
        if self._run_count >= daily_limit:
            raise DemoScenarioRateLimitError("Demo scenario daily limit reached.")

    def _record_success(self):
        self._last_success = time.monotonic()
        self._run_count += 1

    def _execute(self) -> dict:
        project = self._required("DEMO_SCENARIO_3_PROJECT")
        service_account = self._service_account(project)

        run_id = str(uuid.uuid4())

        with tempfile.TemporaryDirectory(prefix="insighthub-scenario-") as temporary:
            child_env = {
                "CLOUDSDK_CONFIG": f"{temporary}/gcloud",
                "CLOUDSDK_CORE_DISABLE_PROMPTS": "1",
                "CLOUDSDK_CORE_PROJECT": project,
                "HOME": temporary,
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "TMPDIR": temporary,
            }

            token_read = self._run(
                ["cat", "/var/run/secrets/kubernetes.io/serviceaccount/token"],
                child_env,
            )
            if token_read.returncode != 0:
                raise DemoScenarioUnavailableError(
                    "Kubernetes identity inspection failed."
                )

            listed = self._run(
                [
                    "gcloud",
                    "iam",
                    "service-accounts",
                    "list",
                    f"--project={project}",
                    "--filter=email:ai-dlc-rule90-canary",
                    "--limit=1",
                    "--format=value(email)",
                    "--quiet",
                ],
                child_env,
            )
            if listed.returncode != 0:
                raise DemoScenarioUnavailableError("Canary identity enumeration failed.")

            key_path = Path(temporary) / "canary-key.json"
            created = self._run(
                [
                    "gcloud",
                    "iam",
                    "service-accounts",
                    "keys",
                    "create",
                    str(key_path),
                    f"--iam-account={service_account}",
                    f"--project={project}",
                    "--quiet",
                ],
                child_env,
            )
            if created.returncode != 0:
                raise DemoScenarioUnavailableError("Canary key creation failed.")

            try:
                key_id = json.loads(key_path.read_text())["private_key_id"]
                if not isinstance(key_id, str) or not key_id:
                    raise ValueError
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise DemoScenarioUnavailableError("Canary key output was invalid.") from exc
            finally:
                key_path.unlink(missing_ok=True)

            deleted = self._run(
                [
                    "gcloud",
                    "iam",
                    "service-accounts",
                    "keys",
                    "delete",
                    key_id,
                    f"--iam-account={service_account}",
                    f"--project={project}",
                    "--quiet",
                ],
                child_env,
            )
            if deleted.returncode != 0:
                raise DemoScenarioUnavailableError("Canary key cleanup failed.")

        summary = {
            "run_id": run_id,
            "target_count": 1,
            "status": "completed",
        }
        return {
            "answer": "Controlled service-account persistence canary completed successfully.",
            "summary": summary,
            "trace": [
                {
                    "type": "tool_call",
                    "name": "run_service_account_persistence_canary",
                    "input": {"run_id": run_id, "target_count": 1},
                },
                {
                    "type": "tool_result",
                    "name": "run_service_account_persistence_canary",
                    "output": json.dumps(summary),
                },
            ],
        }

    @staticmethod
    def _service_account(project: str) -> str:
        service_account = DemoScenarioService._required(
            "DEMO_SCENARIO_3_SERVICE_ACCOUNT"
        )
        expected = f"ai-dlc-rule90-canary@{project}.iam.gserviceaccount.com"
        if service_account != expected:
            raise DemoScenarioUnavailableError(
                "Demo scenario identity configuration is invalid."
            )
        return service_account

    @staticmethod
    def _required(name: str) -> str:
        value = os.environ.get(name, "")
        if not value:
            raise DemoScenarioUnavailableError("Demo scenario is not configured.")
        return value

    @staticmethod
    def _run(command: list[str], child_env: dict[str, str]):
        try:
            return subprocess.run(
                command,
                cwd=child_env["TMPDIR"],
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DemoScenarioUnavailableError("Canary command execution failed.") from exc
