locals {
  name  = "ai-dlc-demo"
  image = var.app_image != "" ? var.app_image : "${var.region}-docker.pkg.dev/${var.project_id}/${local.name}/app:latest"
}

resource "google_artifact_registry_repository" "app" {
  repository_id = local.name
  format        = "DOCKER"
  location      = var.region
  description   = "InsightHub agent application images"

  depends_on = [google_project_service.apis]
}
