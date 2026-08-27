import importlib.util
import json
from pathlib import Path

import apache_beam as beam


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PIPELINE_FILE = (
    PROJECT_ROOT
    / "finstream-gcp"
    / "dataflow"
    / "transactions_pipeline.py"
)


spec = importlib.util.spec_from_file_location(
    "transactions_pipeline",
    PIPELINE_FILE,
)

transactions_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transactions_pipeline)

ValidateTransaction = (
    transactions_pipeline.ValidateTransaction
)


def valid_transaction():
    return {
        "transaction_id": "TX-001",
        "client_id": "CLI-1001",
        "account_id": "ACC-10001",
        "amount": 125.50,
        "currency": "EUR",
        "tx_type": "CARD_PAYMENT",
        "timestamp": "2026-08-27T10:00:00+00:00",
        "merchant_category": "GROCERY",
        "device_id": "device-001",
        "is_flagged_fraud": False,
    }


def test_valid_transaction_is_accepted():

    transaction = valid_transaction()

    message = json.dumps(
        transaction
    ).encode("utf-8")

    validator = ValidateTransaction()

    results = list(
        validator.process(message)
    )

    assert len(results) == 1
    assert results[0] == transaction


def test_missing_required_field_goes_to_dlq():

    transaction = valid_transaction()

    del transaction["client_id"]

    message = json.dumps(
        transaction
    ).encode("utf-8")

    validator = ValidateTransaction()

    results = list(
        validator.process(message)
    )

    assert len(results) == 1

    result = results[0]

    assert isinstance(
        result,
        beam.pvalue.TaggedOutput,
    )

    assert result.tag == "invalid"

    payload = json.loads(
        result.value.decode("utf-8")
    )

    assert "Champs obligatoires manquants" in (
        payload["error"]
    )


def test_non_numeric_amount_goes_to_dlq():

    transaction = valid_transaction()

    transaction["amount"] = "125.50"

    message = json.dumps(
        transaction
    ).encode("utf-8")

    validator = ValidateTransaction()

    results = list(
        validator.process(message)
    )

    result = results[0]

    assert isinstance(
        result,
        beam.pvalue.TaggedOutput,
    )

    payload = json.loads(
        result.value.decode("utf-8")
    )

    assert (
        payload["error"]
        == "amount doit être numérique"
    )


def test_invalid_json_goes_to_dlq():

    message = b'{"transaction_id": invalid-json}'

    validator = ValidateTransaction()

    results = list(
        validator.process(message)
    )

    result = results[0]

    assert isinstance(
        result,
        beam.pvalue.TaggedOutput,
    )

    assert result.tag == "invalid"

    payload = json.loads(
        result.value.decode("utf-8")
    )

    assert "error" in payload
    assert "original_message" in payload