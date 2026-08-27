variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "fintech-data-platform-dev"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "enable_composer" {
  description = "Whether to deploy the Cloud Composer environment"
  type        = bool
  default     = false
}