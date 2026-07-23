# Terraform and Wiz code-to-cloud mapping

This root uses a complete, committed GCS backend declaration so Wiz can map its
Terraform resource declarations to state and then to live GCP resources:

`gs://lucas-argolis-tfstate-1/ai-agent-demo/default.tfstate`

The state bucket is in the Wiz-connected GCP folder. The inherited Wiz service
account has the folder-level `wiz_security_role_terraform_scanning_ext` role,
including bucket read/list and read access to objects ending in `.tfstate`.

The GitHub repository must remain connected to Wiz with IaC scanning enabled.
The `wizcli scan dir` CI step reports IaC findings, but state-based correlation
is performed by the VCS and GCP cloud connectors. An `iac_config.wiz` file is not
needed while the backend in `versions.tf` remains fully specified.

## Wiz Defend cloud events

`wiz_defend.tf` creates a project-scoped audit-log export for Wiz without
changing the organization-level Google SecOps pipeline. It routes Admin
Activity, GKE audit, and enabled Data Access events through a dedicated Pub/Sub
topic and subscription. Cloud Storage Admin Read, Data Read, and Data Write
audit logs are enabled for the project so access to the synthetic customer-data
bucket is observable. Wiz's documented exclusions reduce noisy Kubernetes and
data-service events.

After applying Terraform, edit the `lucasj-argolis-folder` connector in Wiz,
enable Cloud Events Integration using the Manual deployment method, and enter
the `wiz_audit_logs_topic` and `wiz_audit_logs_subscription_id` outputs.
