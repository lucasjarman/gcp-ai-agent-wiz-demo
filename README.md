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
```

Infrastructure is defined in `terraform/`, and Kubernetes application controls are in `kubernetes/deployment.yaml`. Terraform uses a committed GCS backend declaration so Wiz can correlate source declarations, Terraform state, and live GCP resources.

## Local validation

```sh
python -m pytest app/tests
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
```

## Demo safety

This is an intentionally vulnerable security demo, not a production reference architecture. It includes synthetic PII, vulnerable dependencies, permissive cloud identity, and vulnerable API behavior so Wiz can demonstrate attack-path and remediation workflows. Do not add real customer data or production credentials.
