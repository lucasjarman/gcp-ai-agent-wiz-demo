from executor import IsolatedExecutor


def test_job_manifest_isolated(monkeypatch):
    monkeypatch.setenv("EXECUTOR_IMAGE", "example.test/agent:latest")
    executor = IsolatedExecutor()

    manifest = executor.build_job_manifest("agent-exec-test", "sum([1, 2])", [])
    pod_spec = manifest["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["runtimeClassName"] == "gvisor"
    assert manifest["spec"]["activeDeadlineSeconds"] == 85
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
