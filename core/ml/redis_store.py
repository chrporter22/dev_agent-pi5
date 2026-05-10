# /core/ml/redis_store.py

import json
import redis

from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)


def store_json(key, value):

    redis_client.set(
        key,
        json.dumps(value)
    )


def store_value(key, value):

    redis_client.set(
        key,
        value
    )
