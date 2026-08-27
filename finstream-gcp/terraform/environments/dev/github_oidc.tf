resource "google_service_account" "github_deployer" {
  account_id   = "finstream-github-deployer"
  display_name = "FinStream GitHub Actions Deployer"
  project      = data.google_project.current.project_id
}


resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for FinStream GitHub Actions"
  project                   = data.google_project.current.project_id
}


resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"
  project                            = data.google_project.current.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = <<EOT
assertion.repository == "Devince12/finstream-gcp-data-platform"
EOT

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}


resource "google_service_account_iam_member" "github_workload_identity_user" {
  service_account_id = google_service_account.github_deployer.name

  role = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/Devince12/finstream-gcp-data-platform"
}

resource "google_project_iam_member" "github_deployer_dataform_editor" {
  project = data.google_project.current.project_id
  role    = "roles/dataform.editor"

  member = "serviceAccount:${google_service_account.github_deployer.email}"
}