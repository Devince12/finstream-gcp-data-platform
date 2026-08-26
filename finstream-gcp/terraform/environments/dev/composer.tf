resource "google_service_account" "composer" {
  project      = data.google_project.current.project_id
  account_id   = "finstream-composer"
  display_name = "FinStream Composer Service Account"
}

resource "google_project_iam_member" "composer_worker" {
  project = data.google_project.current.project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_iam_member" "composer_bigquery_job_user" {
  project = data.google_project.current.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_iam_member" "composer_bigquery_data_viewer" {
  project = data.google_project.current.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_service" "iamcredentials" {
  project = data.google_project.current.project_id
  service = "iamcredentials.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_iam_member" "composer_dataform_editor" {
  project = data.google_project.current.project_id
  role    = "roles/dataform.editor"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_service_account_iam_member" "composer_can_act_as_dataform" {
  service_account_id = google_service_account.dataform.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.composer.email}"
}