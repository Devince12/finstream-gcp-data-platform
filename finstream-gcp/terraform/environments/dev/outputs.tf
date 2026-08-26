output "project_id" {
  value = data.google_project.current.project_id
}

output "project_number" {
  value = data.google_project.current.number
}

output "data_lake_bucket" {
  value = google_storage_bucket.data_lake.name
}

output "transactions_topic" {
  value = google_pubsub_topic.transactions_stream.name
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.banking.dataset_id
}

output "bigquery_transactions_table" {
  value = google_bigquery_table.transactions_bronze.table_id
}

output "transactions_dlq_topic" {
  value = google_pubsub_topic.transactions_dlq.name
}

output "transactions_dlq_subscription" {
  value = google_pubsub_subscription.transactions_dlq_sub.name
}

output "dataflow_staging_bucket" {
  value = google_storage_bucket.dataflow_staging.name
}

output "bigquery_staging_dataset" {
  value = google_bigquery_dataset.banking_staging.dataset_id
}

output "bigquery_marts_dataset" {
  value = google_bigquery_dataset.banking_marts.dataset_id
}

output "dataform_service_account" {
  value = google_service_account.dataform.email
}

output "composer_service_account" {
  value = google_service_account.composer.email
}

output "composer_environment_name" {
  value = google_composer_environment.finstream.name
}

output "bigquery_ml_dataset" {
  value = google_bigquery_dataset.banking_ml.dataset_id
}