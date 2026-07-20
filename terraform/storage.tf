# GCS bucket holding sensitive customer PII data
resource "google_storage_bucket" "customer_data" {
  name          = "${var.project_id}-customer-data"
  location      = var.region
  force_destroy = true

  # Org policy in this project enforces uniform_bucket_level_access = true.
  # SECURITY ISSUE (still present): no CMEK — default Google-managed encryption only.
  # The over-privileged SA (roles/editor + roles/storage.objectAdmin) is the primary
  # lateral movement finding for this bucket.
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  # No CMEK — relies on Google-managed default encryption only

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_object" "customers_csv" {
  name         = "customers.csv"
  bucket       = google_storage_bucket.customer_data.name
  source       = "${path.root}/../data/customers.csv"
  content_type = "text/csv"
}

resource "google_storage_bucket_object" "employees_csv" {
  name         = "employees.csv"
  bucket       = google_storage_bucket.customer_data.name
  source       = "${path.root}/../data/employees.csv"
  content_type = "text/csv"
}
