resource "google_composer_environment" "finstream" {
  name    = "finstream-composer-dev"
  project = var.project_id
  region  = var.region

  config {
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    software_config {
      image_version = "composer-3-airflow-2"

      env_variables = {
        FINSTREAM_PROJECT_ID  = var.project_id
        FINSTREAM_BQ_LOCATION = "EU"

        FINSTREAM_BRONZE_DATASET = google_bigquery_dataset.banking.dataset_id
        FINSTREAM_BRONZE_TABLE   = google_bigquery_table.transactions_bronze.table_id

        FINSTREAM_GOLD_DATASET            = google_bigquery_dataset.banking_marts.dataset_id
        FINSTREAM_FACT_TRANSACTIONS_TABLE = "fct_transactions"

        FINSTREAM_DATAFORM_REGION     = var.region
        FINSTREAM_DATAFORM_REPOSITORY = "finstream-dataform"
        FINSTREAM_DATAFORM_WORKSPACE  = "dev"
      }
    }

    node_config {
      service_account = google_service_account.composer.email
    }

    workloads_config {
      scheduler {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }

      triggerer {
        cpu       = 0.5
        memory_gb = 1
        count     = 1
      }

      dag_processor {
        cpu        = 1
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }

      web_server {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
      }

      worker {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        min_count  = 1
        max_count  = 3
      }
    }
  }

  depends_on = [
    google_project_iam_member.composer_worker,
    google_project_service.iamcredentials
  ]
}