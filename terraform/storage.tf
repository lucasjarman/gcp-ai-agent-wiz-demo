# GCS bucket holding sensitive customer PII data
resource "google_storage_bucket" "customer_data" {
  name          = "${var.project_id}-customer-data"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
  public_access_prevention = "enforced"

  versioning {
    enabled = true
  }

  # Default Google-managed encryption. For production, use CMEK with key management policies
  encryption {
    default_kms_key_name = ""
  }

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
