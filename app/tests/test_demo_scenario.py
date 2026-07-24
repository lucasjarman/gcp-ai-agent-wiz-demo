import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from demo_scenario import (
    DemoScenarioAuthorizationError,
    DemoScenarioService,
    DemoScenarioUnavailableError,
)


TRIGGER = "Run the approved InsightHub sensitive-data canary."
TOKEN = "test-operator-token"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


CANARY_SERVICE_ACCOUNT = (
    "ai-dlc-rule90-canary@canary-project.iam.gserviceaccount.com"
)


def configure_scenario(monkeypatch):
    monkeypatch.setenv("DEMO_SCENARIOS_ENABLED", "true")
    monkeypatch.setenv("DEMO_SCENARIO_3_PROMPT_SHA256", digest(TRIGGER))
    monkeypatch.setenv("DEMO_SCENARIO_3_TOKEN_SHA256", digest(TOKEN))
    monkeypatch.setenv("DEMO_SCENARIO_3_PROJECT", "canary-project")
    monkeypatch.setenv("DEMO_SCENARIO_3_SERVICE_ACCOUNT", CANARY_SERVICE_ACCOUNT)
    monkeypatch.setenv("DEMO_SCENARIO_COOLDOWN_SECONDS", "0")


def test_non_trigger_prompt_is_not_intercepted(monkeypatch):
    configure_scenario(monkeypatch)
    service = DemoScenarioService()

    assert asyncio.run(service.maybe_run("Show me customer totals", [], None)) is None


def test_trigger_requires_empty_history_and_operator_token(monkeypatch):
    configure_scenario(monkeypatch)
    service = DemoScenarioService()

    assert (
        asyncio.run(
            service.maybe_run(
                TRIGGER,
                [{"role": "user", "content": "before"}],
                TOKEN,
            )
        )
        is None
    )

    try:
        asyncio.run(service.maybe_run(TRIGGER, [], "wrong-token"))
        raise AssertionError("Expected the invalid operator token to be rejected")
    except DemoScenarioAuthorizationError:
        pass


def test_scenario_uses_only_fixed_commands(monkeypatch):
    configure_scenario(monkeypatch)
    service = DemoScenarioService()
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1:5] == ["iam", "service-accounts", "keys", "create"]:
            Path(command[5]).write_text(json.dumps({"private_key_id": "test-key-id"}))
        return type("Completed", (), {"returncode": 0, "stderr": b""})()

    with patch("demo_scenario.subprocess.run", side_effect=fake_run):
        result = asyncio.run(service.maybe_run(TRIGGER, [], TOKEN))

    assert result["trace"][0]["name"] == "run_service_account_persistence_canary"
    assert result["trace"][1]["name"] == "run_service_account_persistence_canary"
    assert result["summary"]["target_count"] == 1
    assert len(commands) == 4
    assert commands[0] == [
        "cat",
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
    ]
    assert commands[1][:4] == ["gcloud", "iam", "service-accounts", "list"]
    assert commands[1][4:] == [
        "--project=canary-project",
        "--filter=email:ai-dlc-rule90-canary",
        "--limit=1",
        "--format=value(email)",
        "--quiet",
    ]
    assert commands[2][:6] == [
        "gcloud",
        "iam",
        "service-accounts",
        "keys",
        "create",
        commands[2][5],
    ]
    assert commands[2][6:] == [
        f"--iam-account={CANARY_SERVICE_ACCOUNT}",
        "--project=canary-project",
        "--quiet",
    ]
    assert commands[3] == [
        "gcloud",
        "iam",
        "service-accounts",
        "keys",
        "delete",
        "test-key-id",
        f"--iam-account={CANARY_SERVICE_ACCOUNT}",
        "--project=canary-project",
        "--quiet",
    ]
    assert all(isinstance(argument, str) for command in commands for argument in command)


def test_scenario_rejects_key_creation_failure(monkeypatch):
    configure_scenario(monkeypatch)
    service = DemoScenarioService()
    calls = 0

    def fake_run(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return type("Completed", (), {"returncode": 0, "stderr": b""})()
        return type("Completed", (), {"returncode": 1, "stderr": b"denied"})()

    with patch("demo_scenario.subprocess.run", side_effect=fake_run):
        try:
            asyncio.run(service.maybe_run(TRIGGER, [], TOKEN))
            raise AssertionError("Expected key creation failure to fail the scenario")
        except DemoScenarioUnavailableError:
            pass


def test_scenario_rejects_non_canary_identity_configuration(monkeypatch):
    configure_scenario(monkeypatch)
    monkeypatch.setenv(
        "DEMO_SCENARIO_3_SERVICE_ACCOUNT",
        "other@example.com",
    )
    service = DemoScenarioService()

    try:
        asyncio.run(service.maybe_run(TRIGGER, [], TOKEN))
        raise AssertionError("Expected invalid canary identities to be rejected")
    except DemoScenarioUnavailableError:
        pass
