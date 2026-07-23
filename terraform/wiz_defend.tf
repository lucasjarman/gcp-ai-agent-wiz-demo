resource "google_project_iam_audit_config" "storage_data_access" {
  project = var.project_id
  service = "storage.googleapis.com"

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

resource "google_pubsub_topic" "wiz_audit_logs" {
  project                    = var.project_id
  name                       = "wiz-export-audit-logs"
  message_retention_duration = "86400s"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "wiz_audit_logs" {
  project                    = var.project_id
  name                       = "wiz-export-audit-logs-sub"
  topic                      = google_pubsub_topic.wiz_audit_logs.id
  message_retention_duration = "86400s"

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription_iam_member" "wiz_audit_logs_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.wiz_audit_logs.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${var.wiz_managed_service_account}"
}

resource "google_logging_project_sink" "wiz_audit_logs" {
  project                = var.project_id
  name                   = "wiz-export-project-pubsub"
  description            = "Send project audit logs to Pub/Sub for Wiz Defend"
  destination            = "pubsub.googleapis.com/${google_pubsub_topic.wiz_audit_logs.id}"
  unique_writer_identity = true

  filter = <<-EOT
    log_id("cloudaudit.googleapis.com/activity") OR protoPayload.serviceName="k8s.io" OR log_id("cloudaudit.googleapis.com/data_access")
  EOT

  exclusions {
    name   = "exclude-non-interesting-events"
    filter = <<-EOT
      protoPayload.methodName!~"^io\.k8s\..*\.(approve|bind|create|delete|deletecollection|escalate|impersonate|patch|post|proxy|put|sign|update)$" AND protoPayload.methodName!~"^io\.k8s.*secrets\.(get|list|watch)$" AND resource.type="k8s_cluster"
    EOT
  }

  exclusions {
    name   = "exclude-control-plane-1"
    filter = <<-EOT
      protoPayload.authenticationInfo.principalEmail=~"^system\:" AND protoPayload.authenticationInfo.principalEmail!="system\:anonymous" AND protoPayload.authenticationInfo.principalEmail!~"^system\:serviceaccount"
    EOT
  }

  exclusions {
    name   = "exclude-control-plane-2"
    filter = <<-EOT
      protoPayload.authenticationInfo.principalEmail=~"^system\:serviceaccount\:kube-system"
    EOT
  }

  exclusions {
    name   = "exclude-non-interesting-principals"
    filter = <<-EOT
      protoPayload.authenticationInfo.principalEmail=~".*(-operator|\:operator|\:rancher|\:cert-manager-cainjector|\:prometheus-server|\:domino-platform|\:custom-metrics-stackdriver-adapter|\:composer-system|\:observe-metrics|\:rbac-manager)$"
    EOT
  }

  exclusions {
    name   = "exclude-non-interesting-resources"
    filter = <<-EOT
      (protoPayload.methodName=~"^io\.k8s\..*(leases|selfsubjectrulesreviews|subjectaccessreviews|tokenreviews|selfsubjectaccessreviews).*" OR protoPayload.methodName=~"^io\.k8s\..*\.events\.patch$" OR protoPayload.methodName=~"^io\.k8s\..*\.services\.proxy\..*" OR protoPayload.methodName=~"^io\.k8s\..*\.status\.(patch|update)$") AND resource.type="k8s_cluster"
    EOT
  }

  exclusions {
    name   = "exclude-noisy-data-events-services"
    filter = <<-EOT
      protoPayload.authorizationInfo.permissionType=~"(DATA_READ|DATA_WRITE)" AND protoPayload.serviceName=~"(bigtable.googleapis.com|spanner.googleapis.com|monitoring.googleapis.com|dataproc.googleapis.com)"
    EOT
  }
}

resource "google_pubsub_topic_iam_member" "wiz_audit_logs_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.wiz_audit_logs.name
  role    = "roles/pubsub.publisher"
  member  = google_logging_project_sink.wiz_audit_logs.writer_identity
}
