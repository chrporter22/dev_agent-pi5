import time
import redis
from config import RATE_LIMIT, RATE_WINDOW

class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client

    def check(self, user_id):
        key = f"rate:{user_id}"
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, RATE_WINDOW)
        return count <= RATE_LIMIT
