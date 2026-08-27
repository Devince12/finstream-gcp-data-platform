import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from faker import Faker
from google.cloud import pubsub_v1

# ============================================================
# Initialization
# ============================================================

fake = Faker()
load_dotenv()


# ============================================================
# GCP configuration
# ============================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID")

if not PROJECT_ID:
    raise ValueError("GCP_PROJECT_ID is missing from .env")

if not TOPIC_ID:
    raise ValueError("PUBSUB_TOPIC_ID is missing from .env")


publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)


# ============================================================
# Generator configuration
# ============================================================

GENERATOR_MODE = os.getenv(
    "GENERATOR_MODE",
    "stream",
).lower()

STATE_FILE = os.getenv(
    "GENERATOR_STATE_FILE",
    "finstream_generator_state.json",
)

STREAM_DELAY_SECONDS = float(
    os.getenv(
        "STREAM_DELAY_SECONDS",
        "0.5",
    )
)

BACKFILL_START = os.getenv(
    "BACKFILL_START",
    "2026-08-15T00:00:00+00:00",
)

BACKFILL_END = os.getenv(
    "BACKFILL_END",
    "2026-08-25T23:59:59+00:00",
)

BACKFILL_COUNT = int(
    os.getenv(
        "BACKFILL_COUNT",
        "200000",
    )
)


# ============================================================
# Business reference data
# ============================================================

TX_TYPES = [
    "CARD_PAYMENT",
    "SEPA_TRANSFER",
    "ATM_WITHDRAWAL",
    "MOBILE_MONEY",
]

CURRENCIES = [
    "EUR",
    "USD",
    "GBP",
]

MERCHANT_CATEGORIES = [
    "GROCERY",
    "ELECTRONICS",
    "TRAVEL",
    "GAMBLING",
    "RESTAURANT",
]


# ============================================================
# Simulation configuration
# ============================================================

CLIENT_MIN_ID = 1000
CLIENT_MAX_ID = 9999

# Baseline fraud probability.
BASE_FRAUD_RATE = 0.035

# New devices are possible for normal users too.
NORMAL_NEW_DEVICE_PROBABILITY = 0.03
FRAUD_NEW_DEVICE_PROBABILITY = 0.40

# Rare cases where several clients use the same device.
SHARED_DEVICE_PROBABILITY = 0.01

# A fraud can trigger a short sequence of transactions.
FRAUD_BURST_START_PROBABILITY = 0.30

# Probability of selecting an already compromised client
# for the next transaction.
ACTIVE_BURST_CLIENT_PROBABILITY = 0.30

# Probability that a transaction inside a fraud burst
# is actually fraudulent.
BURST_FRAUD_PROBABILITY = 0.80

STATE_SAVE_INTERVAL = 500


# ============================================================
# Runtime state
# ============================================================

client_profiles = {}

active_fraud_sessions = {}

shared_devices = [
    f"SHARED-{index:04d}"
    for index in range(1, 51)
]


# ============================================================
# Utility functions
# ============================================================

def parse_utc_datetime(value):
    """
    Parse an ISO-8601 datetime and normalize it to UTC.
    """

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def generate_device_id():
    """
    Generate a synthetic device fingerprint.
    """

    raw_value = fake.uuid4()

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()[:12]


# ============================================================
# Persistent state
# ============================================================

def load_state():
    """
    Restore customer/device behavior across generator restarts.
    """

    global client_profiles
    global active_fraud_sessions

    if not os.path.exists(STATE_FILE):
        print(
            f"No existing generator state found: {STATE_FILE}"
        )
        return

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as state_file:

            state = json.load(
                state_file
            )

        client_profiles = state.get(
            "client_profiles",
            {},
        )

        active_fraud_sessions = state.get(
            "active_fraud_sessions",
            {},
        )

        print(
            f"Loaded {len(client_profiles):,} "
            f"persistent customer profiles."
        )

    except Exception as exc:
        raise RuntimeError(
            f"Unable to load generator state: {exc}"
        ) from exc


def save_state():
    """
    Save state atomically so an interruption does not corrupt
    the main state file.
    """

    state = {
        "client_profiles": client_profiles,
        "active_fraud_sessions": active_fraud_sessions,
    }

    temporary_file = (
        f"{STATE_FILE}.tmp"
    )

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as state_file:

        json.dump(
            state,
            state_file,
            indent=2,
        )

    os.replace(
        temporary_file,
        STATE_FILE,
    )


# ============================================================
# Customer profiles
# ============================================================

def create_client_profile(client_id):
    """
    Create a synthetic but persistent banking customer profile.
    """

    number_of_devices = random.choices(
        population=[1, 2, 3],
        weights=[0.65, 0.25, 0.10],
        k=1,
    )[0]

    devices = [
        generate_device_id()
        for _ in range(number_of_devices)
    ]

    number_of_accounts = random.choices(
        population=[1, 2, 3],
        weights=[0.70, 0.25, 0.05],
        k=1,
    )[0]

    accounts = [
        f"ACC-{random.randint(10000, 99999)}"
        for _ in range(number_of_accounts)
    ]

    preferred_currency = random.choice(
        CURRENCIES
    )

    preferred_tx_types = random.sample(
        TX_TYPES,
        k=random.randint(1, 3),
    )

    return {
        "client_id": client_id,
        "devices": devices,
        "accounts": accounts,
        "preferred_currency": preferred_currency,
        "preferred_tx_types": preferred_tx_types,
    }


def get_client_profile(client_id):

    if client_id not in client_profiles:
        client_profiles[client_id] = (
            create_client_profile(
                client_id
            )
        )

    return client_profiles[
        client_id
    ]


# ============================================================
# Customer selection / fraud burst behavior
# ============================================================

def choose_client():
    """
    Fraud sessions increase the probability that several
    consecutive transactions belong to the same compromised
    customer.
    """

    active_clients = [
        client_id
        for client_id, remaining
        in active_fraud_sessions.items()
        if remaining > 0
    ]

    if (
        active_clients
        and random.random()
        < ACTIVE_BURST_CLIENT_PROBABILITY
    ):
        client_id = random.choice(
            active_clients
        )

        active_fraud_sessions[
            client_id
        ] -= 1

        return client_id, True

    client_id = (
        f"CLI-{random.randint(CLIENT_MIN_ID, CLIENT_MAX_ID)}"
    )

    return client_id, False


def determine_fraud(
    client_id,
    is_burst_transaction,
):
    """
    Fraud is probabilistic rather than determined by a
    single feature.
    """

    if is_burst_transaction:
        is_fraud = (
            random.random()
            < BURST_FRAUD_PROBABILITY
        )
    else:
        is_fraud = (
            random.random()
            < BASE_FRAUD_RATE
        )

    if (
        is_fraud
        and random.random()
        < FRAUD_BURST_START_PROBABILITY
    ):
        active_fraud_sessions[
            client_id
        ] = random.randint(
            2,
            5,
        )

    return is_fraud


# ============================================================
# Amount generation
# ============================================================

def generate_normal_amount():
    """
    Legitimate transactions include small, medium and
    occasional high-value operations.
    """

    bucket = random.random()

    if bucket < 0.70:
        return round(
            random.uniform(
                5,
                300,
            ),
            2,
        )

    if bucket < 0.93:
        return round(
            random.uniform(
                300,
                1500,
            ),
            2,
        )

    if bucket < 0.99:
        return round(
            random.uniform(
                1500,
                7000,
            ),
            2,
        )

    return round(
        random.uniform(
            7000,
            18000,
        ),
        2,
    )


def generate_fraud_amount():
    """
    Fraud and legitimate transaction distributions overlap.

    Amount alone must not perfectly identify fraud.
    """

    bucket = random.random()

    if bucket < 0.25:
        return round(
            random.uniform(
                20,
                500,
            ),
            2,
        )

    if bucket < 0.50:
        return round(
            random.uniform(
                500,
                2500,
            ),
            2,
        )

    if bucket < 0.80:
        return round(
            random.uniform(
                2500,
                9000,
            ),
            2,
        )

    return round(
        random.uniform(
            9000,
            20000,
        ),
        2,
    )


# ============================================================
# Device behavior
# ============================================================

def choose_device(
    profile,
    is_fraud,
):
    """
    Normal customers mainly reuse known devices.

    Fraud is more likely to involve a new device, but not
    systematically.
    """

    if random.random() < SHARED_DEVICE_PROBABILITY:
        return random.choice(
            shared_devices
        )

    if is_fraud:
        new_device_probability = (
            FRAUD_NEW_DEVICE_PROBABILITY
        )
    else:
        new_device_probability = (
            NORMAL_NEW_DEVICE_PROBABILITY
        )

    if (
        random.random()
        < new_device_probability
    ):
        new_device = generate_device_id()

        profile["devices"].append(
            new_device
        )

        return new_device

    return random.choice(
        profile["devices"]
    )


# ============================================================
# Currency behavior
# ============================================================

def choose_currency(
    profile,
    is_fraud,
):

    preferred_currency = (
        profile["preferred_currency"]
    )

    if is_fraud:
        unusual_currency_probability = 0.35
    else:
        unusual_currency_probability = 0.10

    if (
        random.random()
        < unusual_currency_probability
    ):
        alternatives = [
            currency
            for currency in CURRENCIES
            if currency != preferred_currency
        ]

        return random.choice(
            alternatives
        )

    return preferred_currency


# ============================================================
# Transaction type behavior
# ============================================================

def choose_tx_type(
    profile,
    is_fraud,
):

    if is_fraud:
        unusual_tx_probability = 0.45
    else:
        unusual_tx_probability = 0.15

    if (
        random.random()
        < unusual_tx_probability
    ):
        return random.choice(
            TX_TYPES
        )

    return random.choice(
        profile["preferred_tx_types"]
    )


# ============================================================
# Merchant behavior
# ============================================================

def choose_merchant_category(
    is_fraud,
):

    if is_fraud:
        weights = [
            10,  # GROCERY
            22,  # ELECTRONICS
            20,  # TRAVEL
            33,  # GAMBLING
            15,  # RESTAURANT
        ]

    else:
        weights = [
            30,
            20,
            15,
            10,
            25,
        ]

    return random.choices(
        MERCHANT_CATEGORIES,
        weights=weights,
        k=1,
    )[0]


# ============================================================
# Transaction generation
# ============================================================

def generate_transaction(
    transaction_timestamp=None,
):
    """
    Generate one banking transaction while preserving
    customer behavioral history.
    """

    if transaction_timestamp is None:
        transaction_timestamp = (
            datetime.now(
                timezone.utc
            )
        )

    (
        client_id,
        is_burst_transaction,
    ) = choose_client()

    profile = get_client_profile(
        client_id
    )

    is_fraud = determine_fraud(
        client_id,
        is_burst_transaction,
    )

    if is_fraud:
        amount = generate_fraud_amount()
    else:
        amount = generate_normal_amount()

    device_id = choose_device(
        profile,
        is_fraud,
    )

    currency = choose_currency(
        profile,
        is_fraud,
    )

    tx_type = choose_tx_type(
        profile,
        is_fraud,
    )

    merchant_category = (
        choose_merchant_category(
            is_fraud
        )
    )

    account_id = random.choice(
        profile["accounts"]
    )

    return {
        "transaction_id": fake.uuid4(),
        "client_id": client_id,
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "tx_type": tx_type,
        "merchant_category": merchant_category,
        "timestamp": (
            transaction_timestamp
            .astimezone(timezone.utc)
            .isoformat()
        ),
        "device_id": device_id,
        "is_flagged_fraud": is_fraud,
    }


# ============================================================
# Pub/Sub helper
# ============================================================

def publish_transaction(
    transaction,
):

    bytes_data = json.dumps(
        transaction
    ).encode("utf-8")

    return publisher.publish(
        topic_path,
        bytes_data,
    )


# ============================================================
# Historical backfill
# ============================================================

def generate_backfill_timestamps(
    start_datetime,
    end_datetime,
    transaction_count,
):
    """
    Generate timestamps first and sort them.

    Transactions are then created in chronological order,
    which is essential for customer behavioral continuity.
    """

    start_timestamp = (
        start_datetime.timestamp()
    )

    end_timestamp = (
        end_datetime.timestamp()
    )

    timestamps = [
        random.uniform(
            start_timestamp,
            end_timestamp,
        )
        for _ in range(
            transaction_count
        )
    ]

    timestamps.sort()

    return [
        datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        )
        for value in timestamps
    ]


def publish_backfill():
    """
    Generate historical data between BACKFILL_START and
    BACKFILL_END.
    """

    start_datetime = parse_utc_datetime(
        BACKFILL_START
    )

    end_datetime = parse_utc_datetime(
        BACKFILL_END
    )

    if start_datetime >= end_datetime:
        raise ValueError(
            "BACKFILL_START must be before BACKFILL_END"
        )

    print(
        "\nFinStream historical backfill"
    )
    print(
        f"Start       : {start_datetime.isoformat()}"
    )
    print(
        f"End         : {end_datetime.isoformat()}"
    )
    print(
        f"Transactions: {BACKFILL_COUNT:,}"
    )

    timestamps = (
        generate_backfill_timestamps(
            start_datetime,
            end_datetime,
            BACKFILL_COUNT,
        )
    )

    pending_futures = []

    try:

        for index, timestamp in enumerate(
            timestamps,
            start=1,
        ):

            transaction = (
                generate_transaction(
                    transaction_timestamp=timestamp
                )
            )

            future = publish_transaction(
                transaction
            )

            pending_futures.append(
                future
            )

            # Wait for batches instead of blocking on
            # every single Pub/Sub message.
            if len(pending_futures) >= 1000:

                for pending_future in (
                    pending_futures
                ):
                    pending_future.result()

                pending_futures.clear()

            if (
                index
                % STATE_SAVE_INTERVAL
                == 0
            ):
                save_state()

            if index % 5000 == 0:
                print(
                    f"{index:,}/{BACKFILL_COUNT:,} "
                    "transactions published"
                )

        # Flush final Pub/Sub messages.
        for pending_future in pending_futures:
            pending_future.result()

        save_state()

        print(
            "\nHistorical backfill completed successfully."
        )

    except KeyboardInterrupt:

        save_state()

        print(
            "\nBackfill interrupted. "
            "State has been saved."
        )


# ============================================================
# Real-time streaming mode
# ============================================================

def publish_stream():
    """
    Generate transactions continuously with current UTC time.
    """

    print(
        "\nFinStream real-time generator"
    )

    print(
        f"Topic: {topic_path}"
    )

    message_count = 0

    try:

        while True:

            transaction = (
                generate_transaction()
            )

            future = publish_transaction(
                transaction
            )

            future.result()

            message_count += 1

            print(
                f"Sent "
                f"[{transaction['tx_type']}] "
                f"Client={transaction['client_id']} | "
                f"Device={transaction['device_id']} | "
                f"Amount={transaction['amount']} "
                f"{transaction['currency']} | "
                f"Fraud={transaction['is_flagged_fraud']}"
            )

            if (
                message_count
                % STATE_SAVE_INTERVAL
                == 0
            ):
                save_state()

            time.sleep(
                STREAM_DELAY_SECONDS
            )

    except KeyboardInterrupt:

        save_state()

        print(
            "\nGenerator stopped. "
            "Customer state has been saved."
        )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    load_state()

    if GENERATOR_MODE == "backfill":

        publish_backfill()

    elif GENERATOR_MODE == "stream":

        publish_stream()

    else:

        raise ValueError(
            "GENERATOR_MODE must be "
            "'stream' or 'backfill'"
        )