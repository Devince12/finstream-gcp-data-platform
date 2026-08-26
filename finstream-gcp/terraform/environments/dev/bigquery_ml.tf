resource "google_bigquery_dataset" "banking_ml" {
  project    = var.project_id
  dataset_id = "banking_ml"
  location   = "EU"

  description = "FinStream machine learning dataset for fraud detection"

  delete_contents_on_destroy = false
}