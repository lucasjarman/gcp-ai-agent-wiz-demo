resource "google_service_account" "persistence_canary" {
  project      = var.project_id
  account_id   = "ai-dlc-rule90-canary"
  display_name = "InsightHub rule 90 canary"
  description  = "Role-less identity used only by controlled Wiz correlation demo 90"

  depends_on = [google_project_service.apis]
}

resource "google_service_account_iam_member" "app_can_manage_persistence_canary_keys" {
  service_account_id = google_service_account.persistence_canary.name
  role               = "roles/iam.serviceAccountKeyAdmin"
  member             = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_audit_config" "iam_data_access" {
  project = var.project_id
  service = "iam.googleapis.com"

  audit_log_config {
    log_type = "ADMIN_READ"
  }

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }
}
