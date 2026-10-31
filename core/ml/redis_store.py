# /core/ml/redis_store.py

import json
import redis

from config import (
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USER
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
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
