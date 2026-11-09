from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request

from .errors import APIError

WINDOW_S = 60
ASK_LIMIT = 10
QUEST_LIMIT = 10


class RateLimiter:
    def __init__(self, limit):
        self.limit = limit
        self.hits = defaultdict(deque)
        self.lock = Lock()

    def check(self, key):
        now = monotonic()
        with self.lock:
            hits = self.hits[key]
            while hits and now - hits[0] >= WINDOW_S:
                hits.popleft()
            if len(hits) >= self.limit:
                raise APIError("too_many_requests", "Too many requests. Please wait a minute and try again.", 429)
            hits.append(now)


def client_address(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def limit_ask(request: Request):
    request.app.state.ask_limiter.check(client_address(request))


def limit_quest_creation(request: Request):
    request.app.state.quest_limiter.check(client_address(request))
