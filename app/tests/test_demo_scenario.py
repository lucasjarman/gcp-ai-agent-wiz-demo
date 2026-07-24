import asyncio
import hashlib
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


CANARY_SERVICE_ACCOUNTS = [
    f"ai-dlc-rule93-canary-{index}@canary-project.iam.gserviceaccount.com"
    for index in range(1, 4)
]


def configure_scenario(monkeypatch):
    monkeypatch.setenv("DEMO_SCENARIOS_ENABLED", "true")
    monkeypatch.setenv("DEMO_SCENARIO_3_PROMPT_SHA256", digest(TRIGGER))
    monkeypatch.setenv("DEMO_SCENARIO_3_TOKEN_SHA256", digest(TOKEN))
    monkeypatch.setenv("DEMO_SCENARIO_3_PROJECT", "canary-project")
    monkeypatch.setenv("DEMO_SCENARIO_3_SERVICE_ACCOUNTS", ",".join(CANARY_SERVICE_ACCOUNTS))
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


def test_scenario_uses_only_fixed_gcloud_commands(monkeypatch):
    configure_scenario(monkeypatch)
    service = DemoScenarioService()
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return type("Completed", (), {"returncode": 0})()

    with patch("demo_scenario.subprocess.run", side_effect=fake_run):
        result = asyncio.run(service.maybe_run(TRIGGER, [], TOKEN))

    assert result["trace"][0]["name"] == "run_identity_lateral_movement_canary"
    assert result["trace"][1]["name"] == "run_identity_lateral_movement_canary"
    assert result["summary"]["target_count"] == 3
    assert len(commands) == 4
    assert commands[0][:4] == ["gcloud", "iam", "service-accounts", "list"]
    assert commands[0][4:] == [
        "--project=canary-project",
        "--filter=email:ai-dlc-rule93-canary-",
        "--limit=3",
        "--format=value(email)",
        "--quiet",
    ]
    for command, service_account in zip(commands[1:], CANARY_SERVICE_ACCOUNTS):
        assert command == [
            "gcloud",
            f"--impersonate-service-account={service_account}",
            "auth",
            "print-access-token",
            "--quiet",
        ]
    assert all(isinstance(argument, str) for command in commands for argument in command)


def test_scenario_rejects_non_canary_identity_configuration(monkeypatch):
    configure_scenario(monkeypatch)
    monkeypatch.setenv(
        "DEMO_SCENARIO_3_SERVICE_ACCOUNTS",
        ",".join([*CANARY_SERVICE_ACCOUNTS[:2], "other@example.com"]),
    )
    service = DemoScenarioService()

    try:
        asyncio.run(service.maybe_run(TRIGGER, [], TOKEN))
        raise AssertionError("Expected invalid canary identities to be rejected")
    except DemoScenarioUnavailableError:
        pass
