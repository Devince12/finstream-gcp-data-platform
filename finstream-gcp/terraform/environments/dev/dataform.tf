# ============================================================
# Dataform Service Account
# ============================================================

resource "google_service_account" "dataform" {
  project      = data.google_project.current.project_id
  account_id   = "finstream-dataform"
  display_name = "FinStream Dataform Service Account"
}

# ============================================================
# Dataform BigQuery permissions
# ============================================================

resource "google_project_iam_member" "dataform_bigquery_job_user" {
  project = data.google_project.current.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dataform.email}"
}

resource "google_project_iam_member" "dataform_bigquery_data_editor" {
  project = data.google_project.current.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataform.email}"

  depends_on = [
    google_bigquery_dataset.banking,
    google_bigquery_dataset.banking_staging,
    google_bigquery_dataset.banking_marts,
  ]
}

resource "google_project_iam_member" "dataform_bigquery_data_viewer" {
  project = data.google_project.current.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.dataform.email}"
}

resource "google_service_account_iam_member" "dataform_service_agent_token_creator" {
  service_account_id = google_service_account.dataform.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-dataform.iam.gserviceaccount.com"
}