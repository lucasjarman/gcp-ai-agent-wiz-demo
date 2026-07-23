# Project status

Last updated: 2026-07-23 (Australia/Melbourne)

## Current deployment

- The live application is `https://agent.ljarman.dev` in the
  `lucas-ai-agent-demo` GCP project.
- The FastAPI and LangChain application runs in the `ai-dlc-demo` namespace on
  GKE Autopilot and uses Vertex AI Gemini.
- Cloudflare permits the approved home address and Wiz scanners. The GKE origin
  separately permits Cloudflare origin ranges.
- The Wiz Runtime Sensor is active and sending workload telemetry.
- GitHub Actions provides source and image scanning, commit-SHA image tagging,
  code-to-cloud tagging, deployment, and live smoke testing.

## Current Wiz observations

Verified through Wiz MCP on 2026-07-23:

- The GCP account `lucas-ai-agent-demo` is connected through the healthy,
  enabled folder connector `lucasj-argolis-folder`.
- The connector has Cloud Events Integration disabled:
  `auditLogMonitorEnabled=false` and no audit-log configuration is present.
- The Wiz Defend Ingestion license is active through 2026-12-31 and currently
  reports zero ingestion units used.
- No `GCP_AUDIT_LOGS` or `GCP_GKE_AUDIT_LOGS` events were present for this
  project in the preceding 30 days.
- Runtime Sensor events are flowing. These are a separate telemetry source and
  do not replace GCP control-plane or GKE audit logs.
- The tenant has 162 enabled rules that can consume GCP Audit Logs and 70
  enabled rules that can consume GKE Audit Logs.
- Live GCP verification found the organization-level Google SecOps SST sink
  `sst_multiorg_activity_sink`. It uses `includeChildren=true` and currently
  exports Admin Activity logs from child projects, including this one, to the
  Google-managed `sst-multiorg-139824078319` Pub/Sub project. Preserve this
  pipeline unchanged.
- The live sink filter does not currently include Data Access logs, despite the
  older SecOps workspace note saying it did. The project IAM policy has no
  explicit audit configuration, and no Cloud Storage Data Access events were
  present in the preceding seven days.
- GKE audit events are being generated locally in GCP under the Admin Activity
  log. The application project has no non-default log sink, Pub/Sub topic, or
  Pub/Sub subscription.
- API Security currently shows five Runtime Sensor-discovered endpoints. Red
  Agent successfully ran API DAST and produced two open AI-powered findings on
  `/api/customers`: a Critical SQL/NoSQL injection and High unrestricted access
  to synthetic customer PII and financial data.

## Existing centralized SecOps logging design

The Google SecOps pipeline and the Wiz Defend pipeline are separate consumers.
Preserve the SecOps design when adding Wiz ingestion.

### Layer 1: projects generate logs

- GCP generates Admin Activity logs automatically for projects in the
  organization.
- Data Access logs are opt-in. They are not enabled at organization or folder
  scope and are not enabled for `lucas-ai-agent-demo`, `secops-lucasjarman`, or
  `lucas-argolis-bootstrap-1`.
- `wiz-attack-sim` explicitly enables `ADMIN_READ`, `DATA_READ`, and
  `DATA_WRITE` for `allServices` in its project IAM `auditConfigs`. It is the
  only project currently configured to generate broad Data Access logs.
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

### Phase 1: provision the GCP pipeline as code

1. Add the Wiz GCP cloud-events Terraform configuration to this repository.
   Use project scope, the existing connector's Wiz-managed identity, a dedicated
   Wiz Pub/Sub topic and subscription in the same project, and at least 24 hours
   of message retention.
2. Add a separate Wiz sink with the Wiz Defend log-source filter so it includes
   GCP Admin Activity, GKE audit events, and supported Data Access events, while
   retaining Wiz's documented noise exclusions.
3. Explicitly enable Cloud Storage Data Access audit logging if bucket-access
   telemetry is part of the demo. Routing `data_access` in a sink does not make
   Storage emit logs when the project audit configuration is absent.
4. Add outputs for the topic name and subscription ID required by the Wiz
   connector.
5. Keep the implementation visible in this repository. Prefer vendoring the
   official module or using explicit Terraform resources over hiding the
   resource definitions behind an unpinned remote archive; confirm the final
   choice before implementation because it affects maintenance and Wiz IaC
   source mapping.

Verification before apply:

- `terraform -chdir=terraform fmt -check`
- `terraform -chdir=terraform validate`
- Review the plan for project-only scope, the expected sink, topic,
  subscription, IAM bindings, and no unrelated resource replacement.

### Phase 2: connect Wiz

Edit the existing `lucasj-argolis-folder` connector in Wiz, enable Cloud Events
Integration with the Manual deployment method, and enter the Terraform outputs:

- Topic: `projects/lucas-ai-agent-demo/topics/<topic-name>`
- Subscription ID: `<subscription-id>`

This is a Wiz-side configuration step; creating the GCP resources alone does
not start ingestion.

### Phase 3: validate ingestion

1. Confirm the connector reports `auditLogMonitorEnabled=true`, a populated
   audit-log configuration, and no new connector health issue.
2. Generate a small, benign set of project control-plane, GKE API, and synthetic
   customer-data bucket events.
3. Confirm Wiz receives events with origins `GCP_AUDIT_LOGS` and
   `GCP_GKE_AUDIT_LOGS`, with the correct actor and resource correlation.
4. Confirm at least one enabled detection rule evaluates the new source. A
   deliberate attack simulation is a separate, explicitly approved step.
5. Check Pub/Sub backlog and GCP logging/Pub/Sub volume after 24 hours before
   broadening scope.

## Follow-on options

- Enable GCS Data Access audit logging deliberately if the demo should show
  reads from the synthetic customer-data bucket, then measure the added volume.
  It is not currently configured and the organization SecOps sink does not
  currently route Data Access logs.
- Add Vertex AI request-response log ingestion later. It is a separate private-
  preview pipeline using BigQuery and Pub/Sub, not part of the base GCP Audit
  Logs setup.
- Add VPC Flow Logs or Cloud DNS logs only if a future scenario requires
  cloud-network-plane coverage that the Runtime Sensor does not provide. Use
  their dedicated log-source configurations rather than combining them with
  the audit-log pipeline.
- Add a System Health Issue automation after the pipeline is stable so stopped
  or misconfigured ingestion becomes visible without manual checks.

## Success criteria for the next implementation

- The Terraform plan contains only the intended logging, Pub/Sub, and IAM
  resources.
- The existing GCP connector remains healthy and has Cloud Events Integration
  enabled.
- New GCP and GKE audit events appear in Wiz for `lucas-ai-agent-demo`.
- Runtime Sensor events continue to flow and the application remains healthy.
- No folder-wide logging or new attack simulation is introduced implicitly.
