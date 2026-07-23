variable "app_image" {
  description = "Full container image URI overriding the default Artifact Registry path"
  type        = string
  default     = ""
}

variable "folder_id" {
  description = "GCP folder containing the project and inherited Wiz connector"
  type        = string
  default     = "430822886237"
}

variable "github_repository" {
  description = "GitHub repository allowed to impersonate the CI service account"
  type        = string
  default     = "lucasjarman/gcp-ai-agent-wiz-demo"
}

variable "org_id" {
  description = "GCP organization ID"
  type        = string
  default     = "139824078319"
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for application resources"
  type        = string
  default     = "australia-southeast1"
}

variable "wiz_managed_service_account" {
  description = "Wiz-managed service account that consumes the audit-log subscription"
  type        = string
  default     = "wizfe70947d83370744c817c10f340@prod-us36.iam.gserviceaccount.com"
}
