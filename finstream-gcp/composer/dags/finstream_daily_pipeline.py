import os
import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator
from airflow.providers.google.cloud.operators.dataform import (
    DataformCreateCompilationResultOperator,
    DataformCreateWorkflowInvocationOperator,
)


# ============================================================
# Environment configuration
# ============================================================

PROJECT_ID = os.environ["FINSTREAM_PROJECT_ID"]
BQ_LOCATION = os.environ["FINSTREAM_BQ_LOCATION"]

BRONZE_DATASET = os.environ["FINSTREAM_BRONZE_DATASET"]
BRONZE_TABLE = os.environ["FINSTREAM_BRONZE_TABLE"]

GOLD_DATASET = os.environ["FINSTREAM_GOLD_DATASET"]
FACT_TRANSACTIONS_TABLE = os.environ[
    "FINSTREAM_FACT_TRANSACTIONS_TABLE"
]

DATAFORM_REGION = os.environ["FINSTREAM_DATAFORM_REGION"]
DATAFORM_REPOSITORY = os.environ["FINSTREAM_DATAFORM_REPOSITORY"]
DATAFORM_WORKSPACE = os.environ["FINSTREAM_DATAFORM_WORKSPACE"]


DATAFORM_WORKSPACE_PATH = (
    f"projects/{PROJECT_ID}/locations/{DATAFORM_REGION}/"
    f"repositories/{DATAFORM_REPOSITORY}/"
    f"workspaces/{DATAFORM_WORKSPACE}"
)


# ============================================================
# Retry policy
# ============================================================

DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
}


# ============================================================
# DAG definition
# ============================================================

with DAG(
    dag_id="finstream_daily_pipeline",
    description=(
        "FinStream daily orchestration pipeline for "
        "Dataform transformations and BigQuery freshness checks"
    ),
    start_date=pendulum.datetime(
        2026,
        8,
        25,
        tz="UTC",
    ),
    schedule="0 0 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=[
        "finstream",
        "bigquery",
        "dataform",
    ],
) as dag:

    # ========================================================
    # Start
    # ========================================================

    start = EmptyOperator(
        task_id="start"
    )

    # ========================================================
    # 1. Check Bronze availability
    # ========================================================

    check_bronze_data = BigQueryCheckOperator(
        task_id="check_bronze_data",
        sql=f"""
        SELECT
            COUNT(*) > 0
        FROM
            `{PROJECT_ID}.{BRONZE_DATASET}.{BRONZE_TABLE}`
        """,
        use_legacy_sql=False,
        location=BQ_LOCATION,
    )

    # ========================================================
    # 2. Compile Dataform workspace
    # ========================================================

    create_compilation_result = (
        DataformCreateCompilationResultOperator(
            task_id="create_compilation_result",
            project_id=PROJECT_ID,
            region=DATAFORM_REGION,
            repository_id=DATAFORM_REPOSITORY,
            compilation_result={
                "workspace": DATAFORM_WORKSPACE_PATH,
            },
        )
    )

    # ========================================================
    # 3. Execute Dataform workflow
    # ========================================================

    run_dataform_workflow = (
        DataformCreateWorkflowInvocationOperator(
            task_id="run_dataform_workflow",
            project_id=PROJECT_ID,
            region=DATAFORM_REGION,
            repository_id=DATAFORM_REPOSITORY,
            workflow_invocation={
                "compilation_result": (
                    "{{ task_instance.xcom_pull("
                    "'create_compilation_result'"
                    ")['name'] }}"
                )
            },
        )
    )

    # ========================================================
    # 4. Check Gold freshness
    #
    # Detailed quality checks are handled by Dataform
    # assertions (uniqueKey, nonNull, rowConditions).
    # Composer only verifies that Gold is recent enough.
    # ========================================================

    check_gold_freshness = BigQueryCheckOperator(
        task_id="check_gold_freshness",
        sql=f"""
        SELECT
            MAX(transaction_timestamp)
                >= TIMESTAMP_SUB(
                    CURRENT_TIMESTAMP(),
                    INTERVAL 24 HOUR
                )
        FROM
            `{PROJECT_ID}.{GOLD_DATASET}.{FACT_TRANSACTIONS_TABLE}`
        """,
        use_legacy_sql=False,
        location=BQ_LOCATION,
    )

    # ========================================================
    # End
    # ========================================================

    end = EmptyOperator(
        task_id="end"
    )

    # ========================================================
    # Dependencies
    # ========================================================

    (
        start
        >> check_bronze_data
        >> create_compilation_result
        >> run_dataform_workflow
        >> check_gold_freshness
        >> end
    )