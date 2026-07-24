locals {
  lateral_canary_service_accounts = {
    one   = "ai-dlc-rule93-canary-1"
    three = "ai-dlc-rule93-canary-3"
    two   = "ai-dlc-rule93-canary-2"
  }
}

resource "google_service_account" "lateral_canary" {
  for_each = local.lateral_canary_service_accounts

  project      = var.project_id
  account_id   = each.value
  display_name = "InsightHub rule 93 canary ${each.key}"
  description  = "Keyless, role-less identity used only by controlled Wiz correlation demo 93"

  depends_on = [google_project_service.apis]
}

resource "google_service_account_iam_member" "app_can_impersonate_lateral_canary" {
  for_each = google_service_account.lateral_canary

  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountTokenCreator"
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
