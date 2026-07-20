terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    # Keep this complete in source: Wiz resolves the backend during VCS scanning
    # and joins its state resources to their declarations and live GCP objects.
    bucket = "lucas-argolis-tfstate-1"
    prefix = "ai-agent-demo"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
