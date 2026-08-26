from google.cloud import pubsub_v1

PROJECT_ID = "fintech-data-platform-dev"
TOPIC_ID = "transactions-stream"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

with open("invalid_transaction.json", "rb") as f:
    message = f.read()

future = publisher.publish(topic_path, message)

print(f"Published message: {future.result()}")