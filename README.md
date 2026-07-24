# GCP AI Agent + Wiz Demo

This repository builds a permanent GCP learning sandbox for demonstrating Wiz across source code, CI/CD, cloud infrastructure, Kubernetes, runtime, and AI workloads.

The live application is an AI customer-data analyst at [agent.ljarman.dev](https://agent.ljarman.dev). Cloudflare restricts access to the home IP and Wiz scanners, while the GKE origin independently permits only Cloudflare traffic.

## Architecture

```text
Cloudflare WAF
  -> GKE Autopilot / FastAPI agent
       -> customer-data tools
       -> bounded Python child processes visible to the Wiz Runtime Sensor
  -> GCP service account and synthetic customer-data bucket

GitHub Actions
  -> Wiz source and image scans
  -> Artifact Registry
  -> wizcli image tag for code-to-cloud mapping
  -> GKE deployment

GCP Audit Logs
  -> project-scoped Logs Router sink
  -> dedicated Pub/Sub topic and subscription
  -> Wiz Defend cloud events (after connector enablement)

Controlled Scenario 3
  -> exact hidden chat prompt + separate operator run token
  -> fixed gcloud commands in the AI workload container
  -> service-account enumeration and disposable canary-key creation
  -> Wiz Sensor + GCP Audit Logs
  -> built-in cross-origin correlation 90
```

Infrastructure is defined in `terraform/`, and Kubernetes application controls are in `kubernetes/deployment.yaml`. Terraform uses a committed GCS backend declaration so Wiz can correlate source declarations, Terraform state, and live GCP resources.

## Local validation

```sh
python -m pytest app/tests
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
```

## Controlled threat scenario

Scenario 3 is disabled unless its digest-only Kubernetes Secret and dedicated
role-less canary identity are present. The exact trigger and operator token
are stored in BWS as `insighthub-scenario-3-prompt` and
`insighthub-scenario-3-run-token`. Enter the trigger into the normal agent chat
with empty history; the browser asks for the operator token only after the
server recognizes the trigger.

The action is deterministic and does not expose a general-purpose cloud or
shell tool. It runs one fixed `gcloud iam service-accounts list` command, then
creates a user-managed key for the dedicated canary service account. The local
key material and the cloud key are deleted immediately after its identifier is
read. This supplies the Sensor and GCP Audit evidence used by the enabled
built-in Wiz correlation `cer-correlation-id-90`. Runs are serialized, limited
to six per UTC day, and have a 30-minute cooldown. Project-level organization
policy exceptions permit this intentionally vulnerable key lifecycle only in
the demo project.

## Demo safety

This is an intentionally vulnerable security demo, not a production reference architecture. It includes synthetic PII, vulnerable dependencies, permissive cloud identity, and vulnerable API behavior so Wiz can demonstrate attack-path and remediation workflows. Do not add real customer data or production credentials.
