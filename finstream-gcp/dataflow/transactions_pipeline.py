import argparse
import json
import os

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from dotenv import load_dotenv
from google.cloud import pubsub_v1


load_dotenv()


# ============================================================
# Validation
# ============================================================

REQUIRED_FIELDS = [
    "transaction_id",
    "client_id",
    "account_id",
    "amount",
    "currency",
    "tx_type",
    "timestamp",
]


class ValidateTransaction(beam.DoFn):

    INVALID = "invalid"

    def process(self, message):

        try:
            transaction = json.loads(
                message.decode("utf-8")
            )

            missing = [
                field
                for field in REQUIRED_FIELDS
                if field not in transaction
            ]

            if missing:
                raise ValueError(
                    f"Champs obligatoires manquants: {missing}"
                )

            if not isinstance(
                transaction["amount"],
                (int, float)
            ):
                raise ValueError(
                    "amount doit être numérique"
                )

            print(
                f"VALID TRANSACTION: "
                f"{transaction['transaction_id']}"
            )

            # Sortie principale
            yield transaction

        except Exception as error:

            dlq_message = {
                "error": str(error),
                "original_message": message.decode(
                    "utf-8",
                    errors="replace"
                ),
            }

            print(
                f"INVALID TRANSACTION: {error}"
            )

            yield beam.pvalue.TaggedOutput(
                self.INVALID,
                json.dumps(dlq_message).encode("utf-8")
            )

# ============================================================
# Publication DLQ
# ============================================================

class PublishToDLQ(beam.DoFn):

    def __init__(self, project_id, dlq_topic):
        self.project_id = project_id
        self.dlq_topic = dlq_topic

    def setup(self):
        self.publisher = pubsub_v1.PublisherClient()

        self.topic_path = self.publisher.topic_path(
            self.project_id,
            self.dlq_topic
        )

    def process(self, message):

        future = self.publisher.publish(
            self.topic_path,
            message
        )

        future.result()

        yield message


# ============================================================
# Pipeline
# ============================================================

def run_pipeline(
    project_id,
    subscription,
    dlq_topic,
    bigquery_dataset,
    bigquery_table,
    pipeline_args=None,
):

    bigquery_table_ref = (
        f"{project_id}:{bigquery_dataset}.{bigquery_table}"
    )

    options = PipelineOptions(
        pipeline_args,
        streaming=True,
        save_main_session=True,
    )

    with beam.Pipeline(options=options) as pipeline:

        messages = (
            pipeline
            | "ReadFromPubSub"
            >> beam.io.ReadFromPubSub(
                subscription=subscription
            )
        )

        results = (
            messages
            | "ValidateTransactions"
            >> beam.ParDo(
                ValidateTransaction()
            ).with_outputs(
                ValidateTransaction.INVALID,
                main="valid",
            )
        )
        valid_transaction = results.valid
        invalid_transaction = results.invalid

        # ====================================================
        # VALID → BigQuery
        # ====================================================

        (
            valid_transaction
            | "WriteTransactionsToBigQuery"
            >> beam.io.WriteToBigQuery(
                bigquery_table_ref,

                schema={
                    "fields": [
                        {
                            "name": "transaction_id",
                            "type": "STRING",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "client_id",
                            "type": "STRING",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "account_id",
                            "type": "STRING",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "amount",
                            "type": "NUMERIC",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "currency",
                            "type": "STRING",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "tx_type",
                            "type": "STRING",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "merchant_category",
                            "type": "STRING",
                        },
                        {
                            "name": "timestamp",
                            "type": "TIMESTAMP",
                            "mode": "REQUIRED",
                        },
                        {
                            "name": "device_id",
                            "type": "STRING",
                        },
                        {
                            "name": "is_flagged_fraud",
                            "type": "BOOLEAN",
                        },
                    ]
                },

                write_disposition=(
                    beam.io.BigQueryDisposition.WRITE_APPEND
                ),

                create_disposition=(
                    beam.io.BigQueryDisposition.CREATE_NEVER
                ),
            )
        )

        # ====================================================
        # INVALID → DLQ
        # ====================================================

        (
            invalid_transaction
            | "PublishInvalidTransactionsToDLQ"
            >> beam.ParDo(
                PublishToDLQ(
                    project_id,
                    dlq_topic
                )
            )
        )


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
    allow_abbrev=False
    )

    parser.add_argument(
        "--project_id",
        default=os.getenv("GCP_PROJECT_ID"),
    )

    parser.add_argument(
        "--subscription",
        default=os.getenv("PUBSUB_SUBSCRIPTION"),
    )

    parser.add_argument(
        "--dlq_topic",
        default=os.getenv("PUBSUB_DLQ_TOPIC_ID"),
    )

    parser.add_argument(
        "--bigquery_dataset",
        default=os.getenv("BIGQUERY_DATASET"),
    )

    parser.add_argument(
        "--bigquery_table",
        default=os.getenv("BIGQUERY_TABLE"),
    )

    args, pipeline_args = parser.parse_known_args()

    required = {
        "project_id": args.project_id,
        "subscription": args.subscription,
        "dlq_topic": args.dlq_topic,
        "bigquery_dataset": args.bigquery_dataset,
        "bigquery_table": args.bigquery_table,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Configuration manquante: "
            + ", ".join(missing)
        )

    print("====================================")
    print("FinStream Dataflow")
    print("====================================")
    print(f"Project      : {args.project_id}")
    print(f"Subscription : {args.subscription}")
    print(f"DLQ topic    : {args.dlq_topic}")
    print(
        f"BigQuery     : "
        f"{args.bigquery_dataset}.{args.bigquery_table}"
    )
    print("====================================")

    run_pipeline(
        project_id=args.project_id,
        subscription=args.subscription,
        dlq_topic=args.dlq_topic,
        bigquery_dataset=args.bigquery_dataset,
        bigquery_table=args.bigquery_table,
        pipeline_args=pipeline_args,
    )


if __name__ == "__main__":
    main()