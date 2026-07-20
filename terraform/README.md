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
