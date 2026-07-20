import base64
import json
import os
import time
import uuid

from kubernetes import client, config


class IsolatedExecutor:
    def __init__(self):
        self.enabled = os.environ.get("EXECUTOR_ENABLED", "false").lower() == "true"
        self.image = os.environ.get("EXECUTOR_IMAGE", "")
        self.namespace = os.environ.get("EXECUTOR_NAMESPACE", "ai-agent-exec")
        self.timeout_seconds = int(os.environ.get("EXECUTOR_TIMEOUT_SECONDS", "90"))

    def run_python(self, code: str, data: object | None = None) -> str:
        if not self.enabled:
            return "The isolated Python executor is disabled in this environment."
        if not self.image:
            return "The isolated Python executor image is not configured."

        config.load_incluster_config()
        batch_api = client.BatchV1Api()
        core_api = client.CoreV1Api()
        job_name = f"agent-exec-{uuid.uuid4().hex[:10]}"
        manifest = self.build_job_manifest(job_name, code, data)

        batch_api.create_namespaced_job(self.namespace, manifest)
        deadline = time.monotonic() + self.timeout_seconds

        try:
            while time.monotonic() < deadline:
                job = batch_api.read_namespaced_job_status(job_name, self.namespace)
                if job.status.succeeded:
                    pods = core_api.list_namespaced_pod(
                        self.namespace,
                        label_selector=f"job-name={job_name}",
                    ).items
                    if not pods:
                        return "Execution completed without a readable result."
                    output = core_api.read_namespaced_pod_log(
                        pods[0].metadata.name,
                        self.namespace,
                    )
                    return output[-8000:]
                if job.status.failed:
                    return "The isolated execution job failed."
                time.sleep(0.5)
            return "The isolated execution job exceeded its time limit."
        finally:
            batch_api.delete_namespaced_job(
                job_name,
                self.namespace,
                propagation_policy="Background",
            )

    def build_job_manifest(self, job_name: str, code: str, data: object | None) -> dict:
        encoded_code = base64.b64encode(code.encode()).decode()
        encoded_data = base64.b64encode(json.dumps(data or []).encode()).decode()

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "labels": {"app": "ai-agent-executor"},
            },
            "spec": {
                "activeDeadlineSeconds": max(15, self.timeout_seconds - 5),
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 60,
                "template": {
                    "metadata": {"labels": {"app": "ai-agent-executor"}},
                    "spec": {
                        "automountServiceAccountToken": False,
                        "restartPolicy": "Never",
                        "runtimeClassName": "gvisor",
                        "serviceAccountName": "executor",
                        "containers": [
                            {
                                "name": "python",
                                "image": self.image,
                                "command": ["python", "/app/sandbox_runner.py"],
                                "env": [
                                    {"name": "PYTHON_CODE_B64", "value": encoded_code},
                                    {"name": "PYTHON_DATA_B64", "value": encoded_data},
                                ],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "256Mi"},
                                },
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "capabilities": {"drop": ["ALL"]},
                                    "readOnlyRootFilesystem": True,
                                    "runAsGroup": 65532,
                                    "runAsNonRoot": True,
                                    "runAsUser": 65532,
                                    "seccompProfile": {"type": "RuntimeDefault"},
                                },
                            }
                        ],
                    },
                },
            },
        }
