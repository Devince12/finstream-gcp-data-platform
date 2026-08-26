# FinStream GCP Data Platform

End-to-end fintech data platform built on Google Cloud Platform for real-time transaction ingestion, analytics, orchestration, fraud detection, and BI reporting.

## Overview

FinStream simulates a banking transaction platform and implements a complete cloud data architecture:

- real-time transaction generation
- Pub/Sub event streaming
- Apache Beam / Dataflow processing
- BigQuery Bronze / staging / marts layers
- Dataform transformations and assertions
- Cloud Composer / Apache Airflow orchestration
- BigQuery ML fraud detection
- Looker Studio executive and risk dashboards
- Terraform infrastructure as code

## Architecture

```text
Transaction Producer
        |
        v
     Pub/Sub
        |
        v
    Dataflow
        |
        v
 BigQuery Bronze
        |
        v
     Dataform
   /     |      \
Staging Marts   ML Features
         |          |
         v          v
 Presentation   BigQuery ML
                    |
                    v
             Fraud Predictions
                    |
          +---------+---------+
          |                   |
          v                   v
   Risk Analytics       Looker Studio

Cloud Composer / Airflow
        |
        +--> Daily orchestration

Terraform
        |
        +--> Infrastructure provisioning

GCP Services
Google Cloud Pub/Sub
Google Cloud Dataflow
Google BigQuery
Google Dataform
Google Cloud Composer
Apache Airflow
BigQuery ML
Google Cloud Storage
IAM
Looker Studio
Data Pipeline
1. Transaction Producer

Synthetic banking transactions are generated and published to Pub/Sub.

The generator includes:

persistent customer profiles
repeated devices per customer
multiple currencies
legitimate and fraudulent transaction overlap
probabilistic fraud behavior
fraud bursts / transaction velocity scenarios
historical backfill and real-time streaming modes
2. Streaming Ingestion

Dataflow consumes Pub/Sub messages and writes validated transactions into BigQuery Bronze.

Invalid records can be routed to a dead-letter flow for further analysis.

3. Data Transformation

Dataform transforms Bronze data into analytics-ready datasets.

Main layers include:

staging
dimensions
fact tables
daily and hourly aggregates
presentation views
ML feature tables

Data quality checks include assertions for:

unique transaction IDs
required fields
business rules
Analytics Layer

Key analytical models include:

fct_transactions
agg_daily_transactions
agg_fraud_daily
agg_transaction_hourly
agg_client_activity
vw_executive_kpis
vw_customer_kpis
vw_risk_kpis
Multi-Currency Handling

Transactions currently support:

EUR
USD
GBP

Financial aggregation is currently implemented without FX conversion.

Currency is therefore preserved as an analytical dimension to prevent invalid cross-currency aggregation.

A future version can introduce dated FX rates and normalized amounts.

Fraud Detection

Fraud detection is implemented using BigQuery ML.

Feature Engineering

Features are constructed point-in-time to avoid look-ahead leakage.

Examples:

transaction amount
currency
transaction type
merchant category
transaction hour
previous transaction count
transactions in the last 1 hour
transactions in the last 24 hours
historical average amount per customer and currency
historical amount standard deviation
amount z-score
new device indicator
previous distinct devices
time since previous transaction

Monetary behavioral features are computed independently per currency.

Dataset Split

The dataset is split chronologically:

TRAIN: August 15–22, 2026
VALIDATION: August 23–24, 2026
TEST: August 25–26, 2026

This avoids random future/past mixing and better simulates a production fraud detection scenario.

Models

Two models were evaluated:

Logistic Regression — baseline
Boosted Tree Classifier — challenger

The Boosted Tree model was selected.

Final Test Performance

Decision threshold: 0.80

Metric	Result
Precision	91.09%
Recall	92.91%
F1 Score	91.99%
Accuracy	99.10%
True Positives	5,663
False Positives	554
False Negatives	432
True Negatives	102,574

The final threshold was selected on the validation dataset before evaluating the untouched test dataset.

Fraud Scoring

The model produces:

fraud probability
predicted fraud flag
risk level

Risk levels:

LOW     < 0.50
MEDIUM  0.50 - 0.79
HIGH    >= 0.80

The resulting table is:

banking_ml.fraud_predictions
Orchestration

Cloud Composer / Apache Airflow executes the daily pipeline.

Schedule:

00:00 UTC every day

Main DAG:

finstream_daily_pipeline

Workflow:

start
  |
  v
check_bronze_data
  |
  v
create_compilation_result
  |
  v
run_dataform_workflow
  |
  v
check_gold_freshness
  |
  v
end

Dataform handles transformations, assertions, ML feature generation, and fraud scoring.

Business Intelligence

Looker Studio provides business-facing dashboards.

Current dashboards include:

Executive / Finance dashboard
Risk / Fraud dashboard

Key KPIs include:

total transaction volume
transaction count
average transaction amount
active customers
fraud rate
fraud transaction count
fraud amount
transaction trends
currency filters
date filters
Infrastructure as Code

Terraform provisions and configures the GCP infrastructure.

Resources include:

BigQuery datasets and tables
Pub/Sub topics and subscriptions
Cloud Storage buckets
IAM service accounts and permissions
Dataform access
Cloud Composer environment
Repository Structure
finstream-gcp/
├── composer/
│   └── dags/
│       └── finstream_daily_pipeline.py
│
├── dataflow/
│   ├── transactions_pipeline.py
│   ├── publish_test.py
│   └── requirements.txt
│
├── dataform/
│   ├── definitions/
│   │   ├── marts/
│   │   ├── ml/
│   │   └── presentation/
│   └── workflow_settings.yaml
│
├── producer/
│   └── transaction_producer.py
│
└── terraform/
    └── environments/
        └── dev/
Security

Sensitive local files are excluded from Git:

.env
Terraform state
Python virtual environments
generated runtime state
credentials and secret files

Service accounts follow scoped IAM permissions for Composer and Dataform.

Current Status

Implemented:

real-time ingestion
historical backfill
Dataflow processing
BigQuery analytics layer
Dataform transformations
data quality assertions
Composer orchestration
daily scheduling
BigQuery ML fraud detection
production-style scoring
Looker Studio dashboards
Terraform infrastructure
Git version control
Future Improvements

Potential next steps:

FX rate normalization
incremental ML feature generation
scheduled model retraining
model drift monitoring
cost monitoring
CI/CD with GitHub Actions
automated Terraform validation
automated Dataform compilation
alerting for high-risk fraud predictions
model registry / promotion workflow
multi-environment dev / staging / prod architecture
Disclaimer

This project uses synthetic banking transaction data for engineering and machine learning demonstration purposes.        