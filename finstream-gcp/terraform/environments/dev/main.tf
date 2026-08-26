data "google_project" "current" {
  project_id = var.project_id
}
resource "google_storage_bucket" "data_lake" {
  name     = "${var.project_id}-data-lake"
  location = "EU"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }

    action {
      type = "Delete"
    }
  }
}

resource "google_pubsub_topic" "transactions_stream" {
  name    = "transactions-stream"
  project = var.project_id
}

resource "google_pubsub_subscription" "transactions_stream_sub" {
  name    = "transactions-stream-sub"
  topic   = google_pubsub_topic.transactions_stream.name
  project = var.project_id

  ack_deadline_seconds = 20

  expiration_policy {
    ttl = ""
  }

  message_retention_duration = "86400s"
}

resource "google_bigquery_dataset" "banking" {
  dataset_id = "banking_analytics"
  project    = var.project_id
  location   = "EU"

  description = "FinStream banking analytics dataset"
}

resource "google_bigquery_table" "transactions_bronze" {
  dataset_id = google_bigquery_dataset.banking.dataset_id
  project    = var.project_id
  table_id   = "transactions_bronze"

  deletion_protection = false

  schema = <<EOF
[
  {
    "name": "transaction_id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "client_id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "account_id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "amount",
    "type": "NUMERIC",
    "mode": "REQUIRED"
  },
  {
    "name": "currency",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "tx_type",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "merchant_category",
    "type": "STRING"
  },
  {
    "name": "timestamp",
    "type": "TIMESTAMP",
    "mode": "REQUIRED"
  },
  {
    "name": "device_id",
    "type": "STRING"
  },
  {
    "name": "is_flagged_fraud",
    "type": "BOOLEAN"
  }
]
EOF

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = [
    "client_id",
    "tx_type"
  ]
}

resource "google_pubsub_topic" "transactions_dlq" {
  name    = "transactions-stream-dlq"
  project = var.project_id
}

resource "google_pubsub_subscription" "transactions_dlq_sub" {
  name    = "transactions-stream-dlq-sub"
  project = var.project_id
  topic   = google_pubsub_topic.transactions_dlq.id

  message_retention_duration = "604800s"
}

resource "google_storage_bucket" "dataflow_staging" {
  name                        = "${var.project_id}-dataflow-staging"
  project                     = var.project_id
  location                    = "EU"
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }

    condition {
      age = 7
    }
  }
}

resource "google_bigquery_dataset" "banking_staging" {
  dataset_id = "banking_staging"
  project    = var.project_id
  location   = "EU"

  description = "FinStream staging and silver analytics dataset"

  delete_contents_on_destroy = false
}

resource "google_bigquery_dataset" "banking_marts" {
  dataset_id = "banking_marts"
  project    = var.project_id
  location   = "EU"

  description = "FinStream gold analytics and marts dataset"

  delete_contents_on_destroy = false
}