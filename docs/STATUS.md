# Project status

Last updated: 2026-07-24 (Australia/Melbourne)

## Scenario 3 correlation validation

- The no-code Scenario 1 smoke test succeeded. Wiz received the Sensor token
  access event and two successful GKE `create pods exec` audit events.
- Scenario 3 uses an exact hidden chat prompt plus operator token to run fixed
  service-account enumeration and disposable key-creation commands directly
  from the AI workload container.
- GCP exposes `GenerateAccessToken` as a Data Access event but requires it to be
  enabled under `iam.googleapis.com`; the Service Account Credentials API does
  not accept an independent audit configuration.
- The `linux/amd64` container build includes Google Cloud CLI 577.0.0 and all
  25 image tests pass.
- BWS project `wiz-demos` holds separate random values named
  `insighthub-scenario-3-prompt` and `insighthub-scenario-3-run-token`.
  Kubernetes Secret `ai-dlc-demo/insighthub-demo-scenarios` contains only their
  SHA-256 digests.
- The scenario stays in `lucas-ai-agent-demo`; it does not require a new
  project, billing-account attachment, custom Wiz rule, or Wiz write API
  credentials.
- The first live trigger completed at `2026-07-24T01:05:39Z`. Wiz ingested the
  exact Sensor 527/529 events and eight IAM Credentials audit events from the
  app container, but token minting alone left the normalized acting-as field
  empty and could not satisfy rule 93.
- The corrected trigger uses each role-less canary for a fixed IAM read. It
  accepts either success or the exact expected `iam.serviceAccounts.get`
  denial, creating delegated API activity without granting access to data.
- Commit `04ef1ab5654fdb2ca5725cba526d6cf29bb2686c` deployed successfully in
  GitHub Actions run `30058655926`; all build, test, Wiz scan, code-to-cloud,
  GKE rollout, and live smoke-test steps passed.
- Live run `eb41e0ef-8748-49b5-9d7f-f3e3eee45246` completed at
  `2026-07-24T01:26:45Z`. Wiz ingested Sensor 527/529 events from the app
  container and three GCP IAM events with the app GSA as actor and three
  distinct canaries as `actingAs`.
- Rule 93 did not produce its final correlation even though both source streams
  arrived. The exact events did not match the previously suspected ignore rule,
  so that explanation was incorrect.
- The replacement uses enabled built-in correlation
  `cer-correlation-id-90`: Sensor rules 527/528 plus the GCP
  `CreateServiceAccountKey` Admin Activity event. The canary has no roles, and
  each generated key is deleted locally and from IAM immediately.
- Terraform replaced the three rule-93 canaries with
  `ai-dlc-rule90-canary`, granted the app GSA key administration only on that
  canary, and removed the obsolete Token Creator bindings.
- The first rule-90 smoke test was rejected by inherited organization policy
  constraints `iam.managed.disableServiceAccountKeyCreation` and
  `iam.disableServiceAccountKeyCreation`; the scenario therefore defines
  project-level exceptions for this intentionally vulnerable sandbox.
- Live run `feca1bfa-9fac-4676-b489-5071586e14f0` completed at
  `2026-07-24T02:55:41Z`. Wiz received Sensor rules 527 and 528 from the same
  AI app container and the successful GCP `CreateServiceAccountKey` event from
  the app GSA. The matching delete succeeded two seconds later, and the canary
  has zero user-managed keys after the run.
- Rule 90 produced no detection. Its built-in matcher selects Sensor events
  through legacy field `alertTypeDetails.common.alertTypeId`, while the live
  rules 527 and 528 events identify their rule through
  `alertTypeDetails.common.rule.id`. The attack inputs and join fields were
  otherwise present, so this is not addressed with a custom TDR.
- The permanent scenario now starts with a fixed, discarded read of the
  mounted Kubernetes token. Native Sensor rule 265 elevates this behavior in
  AI-agent context; the existing fixed `gcloud` actions then generate Sensor
  rules 527/528 and real GCP key lifecycle audit events on the same workload
  and identity path.

## Current deployment

- The live application is `https://agent.ljarman.dev` in the
  `lucas-ai-agent-demo` GCP project.
- The FastAPI and LangChain application runs in the `ai-dlc-demo` namespace on
  GKE Autopilot and uses Vertex AI Gemini.
- Cloudflare permits the approved home address and Wiz scanners. The GKE origin
  separately permits Cloudflare origin ranges.
- The Wiz Runtime Sensor is active and sending workload telemetry.
- Python analysis runs as a bounded non-root child process of the agent so Wiz
  Runtime Sensor events retain the AI-classified container, pod, identity, and
  exposure context. The child uses a stripped environment, restricted Python
  syntax and imports, Linux resource limits, dropped capabilities, and a wall-
  clock timeout. It intentionally shares the agent pod's network namespace and
  GCP workload identity for this controlled demo.
- GitHub Actions provides source and image scanning, commit-SHA image tagging,
  code-to-cloud tagging, deployment, and live smoke testing.
- The GKE Deployment is 1/1 ready, health and SQL smoke tests pass, and the live
  enterprise-analysis prompt finds all six matching customers, invokes bounded
  Python, and returns the correct `6083.33` average. The retired
  `ai-agent-exec` namespace and its old gVisor Job controls were deleted.

## Current Wiz observations

Wiz-side observations were verified through Wiz MCP on 2026-07-23; the GCP
pipeline state below was also verified directly in GCP:

- The GCP account `lucas-ai-agent-demo` is connected through the healthy,
  enabled folder connector `lucasj-argolis-folder`.
- Cloud Events Integration is enabled on that connector. It reports
  `auditLogMonitorEnabled=true` and references topic
  `projects/lucas-ai-agent-demo/topics/wiz-export-audit-logs` and subscription
  `wiz-export-audit-logs-sub`, with no connector health issues.
- The Wiz Defend Ingestion license is active through 2026-12-31 and currently
  reports zero ingestion units used.
- Runtime Sensor events are flowing. These are a separate telemetry source and
  do not replace GCP control-plane or GKE audit logs.
- Recent Sensor detections on the main app container include both `AI Agent
  Module` and `AI Workload` signals and are attributed to the `ai-dlc-demo`
  Deployment. Raw `RUNTIME_EXECUTION_DATA` for the short-lived
  `sandbox_runner.py` child has not appeared, so per-tool child-process
  attribution remains unverified.
- The tenant has 162 enabled rules that can consume GCP Audit Logs and 70
  enabled rules that can consume GKE Audit Logs.
- Live GCP verification found the organization-level Google SecOps SST sink
  `sst_multiorg_activity_sink`. It uses `includeChildren=true` and currently
  exports Admin Activity logs from child projects, including this one, to the
  Google-managed `sst-multiorg-139824078319` Pub/Sub project. Preserve this
  pipeline unchanged.
- The organization SecOps sink filter does not currently include Data Access
  logs, despite the older SecOps workspace note saying it did. This pipeline
  remains unchanged.
- The application project has a separate Terraform-managed Wiz export:
  `wiz-export-project-pubsub`, topic `wiz-export-audit-logs`, and subscription
  `wiz-export-audit-logs-sub`. The connector is configured to consume it.
- Cloud Storage `ADMIN_READ`, `DATA_READ`, and `DATA_WRITE` audit logging is
  enabled at project scope. A benign `storage.objects.get` by the dev identity
  was verified in both Cloud Audit Logs and the Wiz Pub/Sub subscription.
- GKE audit events are being generated locally in GCP and the Wiz project sink
  includes them using Wiz's documented filter and noise exclusions.
- API Security currently shows five Runtime Sensor-discovered endpoints. Red
  Agent successfully ran API DAST and produced two open AI-powered findings on
  `/api/customers`: a Critical SQL/NoSQL injection and High unrestricted access
  to synthetic customer PII and financial data.
- Wiz discovers the `ai-dlc-demo` GAR registry, repository, and images. The
  connector inherits the registry-scanning extension role, including
  `artifactregistry.repositories.downloadArtifacts`, and has no health issue.
  Matching images have Build and Runtime lifecycle stages but none has Store.
  This is consistent with registry scanning not being set to **All Images**;
  only All Images scans populate Store. Confirm or override the registry's scan
  mode under Inventory > Container Registries > Edit Scan Settings.

## Existing centralized SecOps logging design

The Google SecOps pipeline and the Wiz Defend pipeline are separate consumers.
Preserve the SecOps design when adding Wiz ingestion.

### Layer 1: projects generate logs

- GCP generates Admin Activity logs automatically for projects in the
  organization.
- Data Access logs are opt-in and are not enabled at organization or folder
  scope. `lucas-ai-agent-demo` selectively enables them for Cloud Storage;
  `secops-lucasjarman` and `lucas-argolis-bootstrap-1` do not enable them.
- `wiz-attack-sim` explicitly enables `ADMIN_READ`, `DATA_READ`, and
  `DATA_WRITE` for `allServices` in its project IAM `auditConfigs`. It is the
  only project currently configured to generate broad, all-services Data
  Access logs.
- `lucas-argolis-bootstrap-1` has the `secops-dns-logging` DNS policy attached
  to the `argolis-net` VPC, causing DNS query logs to be generated there.

### Layer 2: organization SST routing

- The organization-level sink is `sst_multiorg_activity_sink` with
  `includeChildren=true`.
- Its destination is the Google-managed topic
  `projects/sst-multiorg-139824078319/topics/sst-multiorg-cloud-activity`.
- The intended design is for its inclusion filter to route both
  `cloudaudit.googleapis.com/activity` and
  `cloudaudit.googleapis.com/data_access`.
- The topic is part of Google-managed Security Signal Transport. The local GCP
  administrator cannot read the topic or its IAM policy, so it is not a
  customer-managed integration point and must not be repurposed for Wiz.

### Layer 3: SecOps acceptance

- Google SecOps has a native backend integration consuming the SST pipeline.
- Its console-managed Export Filter is intended to accept DNS queries, Admin
  Activity, System Event, and Data Access logs.
- Generation, SST routing, and the SecOps Export Filter are independent gates.
  A log reaches SecOps only when the project generates it and both downstream
  filters accept it.

### Layer 4: additional paths

- Security Command Center threat and misconfiguration findings use direct
  ingestion configured when the SecOps tenant was provisioned.
- A project-level Pub/Sub Push feed exists as a redundant Data Access path for
  `wiz-attack-sim`.

### Live discrepancy to retain

On 2026-07-23, a successful organization-scope `gcloud logging sinks describe`
returned an SST sink filter containing only the Admin Activity log. Organization
and folder IAM policies had no audit configuration; `wiz-attack-sim` had the
expected all-services Data Access configuration. This conflicts with the
intended SST filter described above and must be reconciled before relying on
the organization sink for Data Access delivery. It is not a visibility or IAM
error: insufficient access to the managed SST topic produced an explicit
`PERMISSION_DENIED`, while the sink and IAM policy reads succeeded.

## Wiz Defend cloud-log plan

### Scope decision

Do not replace or modify the existing organization-level SecOps sink. It has a
single Google-managed SecOps destination and does not configure the Wiz
connector or give Wiz a Pub/Sub subscription. The GCP admin identity cannot
read that managed topic or its IAM policy, so it is not a reusable Wiz source.

Add a parallel, project-level Wiz export for `lucas-ai-agent-demo`. This reuses
the audit logs already generated by GCP while limiting additional Pub/Sub
volume, billing, and impact. Moving the Wiz sink to folder scope can be a later
decision if every project under folder `430822886237` should be covered.

The Runtime Sensor is already the primary DNS and network telemetry source for
the application workload. Do not add VPC Flow Logs or Cloud DNS ingestion to
the initial Wiz Defend pipeline. Consider those sources later only for a demo
that specifically needs cloud-network-plane visibility beyond Sensor-observed
workload activity.

### Phase 1: provision the GCP pipeline as code — complete

Applied on 2026-07-23 using explicit Terraform resources for direct IaC and
code-to-cloud visibility:

- project sink `wiz-export-project-pubsub` with the documented Wiz Defend
  inclusion filter and six noise exclusions;
- topic `projects/lucas-ai-agent-demo/topics/wiz-export-audit-logs` and
  subscription `wiz-export-audit-logs-sub`, both with 24-hour retention and no
  subscription expiry;
- `roles/pubsub.publisher` for the unique Logs Router writer and
  `roles/pubsub.subscriber` for the existing Wiz-managed identity; and
- Cloud Storage `ADMIN_READ`, `DATA_READ`, and `DATA_WRITE` audit logging.

Terraform applied 6 additions, 0 changes, and 0 destroys. A post-apply plan
reported no changes. A benign synthetic-bucket read was observed in both Cloud
Audit Logs and the new subscription.

### Phase 2: connect Wiz — complete

The existing `lucasj-argolis-folder` connector has Cloud Events Integration
enabled using the Terraform outputs:

- Topic: `projects/lucas-ai-agent-demo/topics/wiz-export-audit-logs`
- Subscription ID: `wiz-export-audit-logs-sub`

### Phase 3: validate ingestion — in progress

1. Generate a small, benign set of project control-plane, GKE API, and synthetic
   customer-data bucket events.
2. Confirm Wiz receives events with origins `GCP_AUDIT_LOGS` and
   `GCP_GKE_AUDIT_LOGS`, with the correct actor and resource correlation.
3. Confirm at least one enabled detection rule evaluates the new source. A
   deliberate attack simulation is a separate, explicitly approved step.
4. Check Pub/Sub backlog and GCP logging/Pub/Sub volume after 24 hours before
   broadening scope.

## Follow-on options

- Review Cloud Storage Data Access volume after 24 hours before enabling audit
  logging for any additional GCP services or projects.
- Add Vertex AI request-response log ingestion later. It is a separate private-
  preview pipeline using BigQuery and Pub/Sub, not part of the base GCP Audit
  Logs setup.
- Add VPC Flow Logs or Cloud DNS logs only if a future scenario requires
  cloud-network-plane coverage that the Runtime Sensor does not provide. Use
  their dedicated log-source configurations rather than combining them with
  the audit-log pipeline.
- Add a System Health Issue automation after the pipeline is stable so stopped
  or misconfigured ingestion becomes visible without manual checks.

## Remaining success criteria

- New GCP and GKE audit events appear in Wiz for `lucas-ai-agent-demo`.
- Fresh runtime telemetry confirms `sandbox_runner.py` is attributed to the
  main `ai-dlc-demo` workload after the 2026-07-23 deployment.
- No folder-wide logging or new attack simulation is introduced implicitly.
