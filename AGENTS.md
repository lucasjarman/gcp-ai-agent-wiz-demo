# AGENTS.md

This file is the operating guide for agents working in this repository. Follow
it together with the user's current instructions. If they conflict, stop and
surface the conflict before changing anything.

## Project purpose

This repository is a permanent GCP learning sandbox and Wiz demonstration. It
deliberately combines an AI agent, tool execution, GKE, vulnerable application
behaviour, synthetic sensitive data, permissive IAM, and known-vulnerable
dependencies so Wiz can demonstrate code-to-cloud, attack-path, runtime, and AI
workload analysis.

It is not a production reference architecture. Do not silently remediate an
intentional finding or harden away a demo path. Explain the tradeoff and get the
user's approval first.

## Current architecture

- Public URL: `https://agent.ljarman.dev`
- GCP project: `lucas-ai-agent-demo`
- Region: `australia-southeast1`
- GKE Autopilot cluster and namespace: `ai-dlc-demo`
- Application: FastAPI and a LangChain agent using Vertex AI Gemini
- Tools: customer search, read-only customer SQL, and bounded Python execution
- Isolation: Python jobs use the gVisor `RuntimeClass`
- Edge: Cloudflare permits the user's approved IPs and Wiz scanners
- Origin: Kubernetes network policy permits only Cloudflare origin ranges
- Delivery: GitHub Actions builds, tests, scans, pushes, tags, deploys, and
  smoke-tests the application

## Repository map

- `app/`: application, static frontend, container definition, and tests
- `terraform/`: GCP infrastructure and the committed remote-state declaration
- `kubernetes/deployment.yaml`: application and execution-job controls
- `.github/workflows/deploy.yml`: CI, Wiz scans, code-to-cloud tagging, deploy,
  and live smoke test
- `README.md`: concise architecture, validation, and demo-safety overview
- `docs/STATUS.md`: durable current state, decisions, known gaps, and next steps
  when that file exists

## How to work

Before editing:

1. State assumptions, scope, and any material tradeoffs.
2. Define a small, verifiable success condition.
3. Inspect `git status` and the relevant code, tests, and delivery path.
4. Ask before making a choice that changes the demo story, live exposure, cost,
   or security posture.

While editing:

- Make the smallest change that satisfies the request.
- Match the existing style; do not refactor adjacent code opportunistically.
- Add or update a focused test for behaviour changes.
- Preserve unrelated and user-authored work in a dirty worktree.
- Do not add speculative abstractions, configuration, or fallback behaviour.
- Keep comments focused on why a non-obvious choice exists.

After editing:

1. Run the narrowest relevant checks, then the broader suite when practical.
2. Review the diff for unrelated changes and accidental secret material.
3. Report what changed, what was verified, and anything still unverified.
4. Update `README.md` when setup or operator behaviour changes. For meaningful
   multi-step work, create or update `docs/STATUS.md` rather than using this
   instruction file as a progress log.

## Validation

Run the checks relevant to the changed area:

```sh
python -m pytest app/tests
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
docker build --platform linux/amd64 -t ai-dlc-demo:test ./app
```

The deployed-agent smoke test uses this exact prompt:

```text
Use SQL to rank customer plans by total monthly revenue.
```

It must produce a successful `run_customer_sql` tool result containing
Enterprise `36500`, Professional `7115`, and Starter `315`. A health-only check
is not sufficient for an agent change.

## Demo safety and secrets

- Use only synthetic data. Never add customer, production, or personal data.
- Never print, commit, or paste secret values into logs, issues, or chat.
- Use BWS for operator-held secrets, GitHub Actions secrets for CI, and the
  existing workload-identity pattern for GCP authentication.
- Do not create service-account keys when workload identity is available.
- The repository contains controlled security-demo material, including a known
  credential finding. Do not reproduce its value or remove/rotate it unless the
  user explicitly asks.
- Do not weaken the Cloudflare allowlist, the Kubernetes Cloudflare-only origin
  policy, or the gVisor execution boundary without explicit approval.

## Wiz and code-to-cloud constraints

- Preserve the fully specified GCS Terraform backend. Wiz uses it to correlate
  Terraform source, state, and live GCP resources.
- Preserve commit-SHA image tags and the post-push `wizcli tag` step. Together
  they map the running image back to the Git commit and CI run.
- Source scans and image scans serve different purposes; do not combine or
  remove one merely because the other passes.
- Kubernetes manifests are applied by CI and do not currently have direct IaC
  source mapping in Wiz. Do not claim that the Deployment itself has Terraform
  code-to-cloud coverage.
- The Wiz Runtime Sensor is managed at cluster level, outside the application
  manifest. Verify it independently when cluster or runtime changes are made.
- Treat known vulnerabilities and broad permissions as demo requirements until
  the user selects a remediation story. New accidental vulnerabilities are not
  automatically acceptable.

## Deployment discipline

Pushing a relevant change to `main` triggers the live deployment workflow.
Before doing so, confirm that the user has authorized deployment and that local
tests pass. After deployment, verify the workflow, rollout, `/health`, and the
full agent smoke test. Do not rely only on a successful image build or pod-ready
status.
