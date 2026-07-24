resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "dns.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "orgpolicy.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_org_policy_policy" "storage_resource_use" {
  name   = "projects/${var.project_id}/policies/compute.storageResourceUseRestrictions"
  parent = "projects/${var.project_id}"

  spec {
    inherit_from_parent = false

    rules {
      values {
        allowed_values = [
          "under:folders/${var.folder_id}",
          "under:organizations/${var.org_id}",
          "under:organizations/700634052600",
        ]
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_org_policy_policy" "allow_service_account_key_creation" {
  name   = "projects/${var.project_id}/policies/iam.managed.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    inherit_from_parent = false

    rules {
      enforce = "FALSE"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_org_policy_policy" "allow_service_account_key_creation_legacy" {
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    inherit_from_parent = false

    rules {
      enforce = "FALSE"
    }
  }

  depends_on = [google_project_service.apis]
}
