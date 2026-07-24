output "artifact_registry_repository" {
  description = "Artifact Registry repository containing application images"
  value       = google_artifact_registry_repository.app.name
}

output "canary_service_account" {
  description = "Role-less service account used by the built-in Wiz correlation 90 demo"
  value       = google_service_account.persistence_canary.email
}

output "data_bucket" {
  description = "GCS bucket name containing synthetic customer data"
  value       = google_storage_bucket.customer_data.name
}

output "github_actions_service_account" {
  description = "Service account used by GitHub Actions through workload identity federation"
  value       = google_service_account.github_actions.email
}

output "gke_cluster_name" {
  description = "GKE Autopilot cluster name"
  value       = google_container_cluster.app.name
}

output "service_account" {
  description = "Over-privileged agent service account shown in the Wiz toxic combination"
  value       = google_service_account.app.email
}

output "workload_identity_provider" {
  description = "Workload identity provider used by GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "wiz_audit_logs_subscription_id" {
  description = "Pub/Sub subscription ID to configure on the Wiz GCP connector"
  value       = google_pubsub_subscription.wiz_audit_logs.name
}

output "wiz_audit_logs_topic" {
  description = "Fully qualified Pub/Sub topic to configure on the Wiz GCP connector"
  value       = google_pubsub_topic.wiz_audit_logs.id
}
