"""Recursos de AWS simulados con moto (DynamoDB y SQS) para los tests de la API y el orquestador."""

from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        db = boto3.resource("dynamodb")
        requests = db.create_table(
            TableName="requests",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}, {"AttributeName": "request_sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}, {"AttributeName": "request_sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )  # fmt: skip
        db.create_table(
            TableName="usage",
            KeySchema=[{"AttributeName": "scope", "KeyType": "HASH"}, {"AttributeName": "usage_date", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "scope", "AttributeType": "S"}, {"AttributeName": "usage_date", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )  # fmt: skip
        sqs = boto3.client("sqs")
        queue_url = sqs.create_queue(QueueName="q")["QueueUrl"]
        yield SimpleNamespace(
            requests=requests,
            usage=db.Table("usage"),
            usage_client=boto3.client("dynamodb"),
            sqs=sqs,
            queue_url=queue_url,
        )


def counter(aws, scope, day):
    item = aws.usage.get_item(Key={"scope": scope, "usage_date": day}).get("Item")
    return int(item["request_count"]) if item else 0
