"""Login throttling with a Redis backend and an in-memory fallback.

The limiter tracks failures by client IP and by an opaque account identifier
(the e-mail lookup hash, never the plaintext address). Blocks are temporary and
progressive; a successful login clears the account counters. If Redis is not
configured, a process-local backend is used (suitable for a single instance and
for tests).
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "operan:login"


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    retry_after: int = 0
    reason: str = ""


class MemoryBackend:
    """Process-local TTL store. Operations contain no awaits and are atomic."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}

    def _live(self, key: str) -> Optional[tuple[int, float]]:
        item = self._data.get(key)
        if item is None:
            return None
        if item[1] <= time.time():
            self._data.pop(key, None)
            return None
        return item

    async def incr(self, key: str, ttl: int) -> int:
        self._live(key)
        value = self._data.get(key, (0, 0.0))[0] + 1
        self._data[key] = (value, time.time() + ttl)
        return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (int(value), time.time() + ttl)

    async def get(self, key: str) -> Optional[str]:
        item = self._live(key)
        return str(item[0]) if item else None

    async def ttl(self, key: str) -> int:
        item = self._live(key)
        if item is None:
            return 0
        return max(0, math.ceil(item[1] - time.time()))

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)

    def reset_local(self) -> None:
        self._data.clear()

    async def reset(self) -> None:
        self.reset_local()

    async def close(self) -> None:
        return None


class RedisBackend:
    """Async Redis backend. The client is created lazily on first use."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None

    def _get_client(self):
        if self._client is None:
            from redis.asyncio import Redis

            self._client = Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        return self._client

    async def incr(self, key: str, ttl: int) -> int:
        client = self._get_client()
        value = await client.incr(key)
        await client.expire(key, ttl)
        return int(value)

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._get_client().set(key, value, ex=ttl)

    async def get(self, key: str) -> Optional[str]:
        return await self._get_client().get(key)

    async def ttl(self, key: str) -> int:
        value = await self._get_client().ttl(key)
        return max(0, int(value))

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._get_client().delete(*keys)

    def reset_local(self) -> None:
        # Never flush shared Redis state from application code or tests.
        return None

    async def reset(self) -> None:
        client = self._get_client()
        async for key in client.scan_iter(f"{_KEY_PREFIX}:*"):
            await client.delete(key)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


def _backend():
    if settings.REDIS_URL:
        return RedisBackend(settings.REDIS_URL)
    return MemoryBackend()


class LoginLimiter:
    def __init__(self, backend) -> None:
        self.backend = backend

    @staticmethod
    def account_key(account_hash: str) -> str:
        return f"{_KEY_PREFIX}:account:{account_hash}"

    @staticmethod
    def ip_key(ip: str) -> str:
        return f"{_KEY_PREFIX}:ip:{ip}"

    def _on_backend_error(self, exc: Exception) -> LimitDecision:
        logger.warning(
            "login rate limit backend unavailable (%s)", type(exc).__name__
        )
        if settings.LOGIN_RATE_LIMIT_FAIL_OPEN:
            return LimitDecision(allowed=True)
        return LimitDecision(allowed=False, retry_after=60, reason="backend_unavailable")

    async def check(self, *, ip: str, account_hash: str) -> LimitDecision:
        try:
            for scope, base_key in (
                ("account", self.account_key(account_hash)),
                ("ip", self.ip_key(ip)),
            ):
                remaining = await self.backend.ttl(f"{base_key}:block")
                if remaining > 0:
                    return LimitDecision(
                        allowed=False, retry_after=remaining, reason=scope
                    )
        except Exception as exc:  # noqa: BLE001 - availability decision is explicit
            return self._on_backend_error(exc)
        return LimitDecision(allowed=True)

    async def record_failure(self, *, ip: str, account_hash: str) -> None:
        try:
            await self._hit(
                self.account_key(account_hash),
                settings.LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS,
            )
            await self._hit(
                self.ip_key(ip),
                settings.LOGIN_RATE_LIMIT_IP_ATTEMPTS,
            )
        except Exception as exc:  # noqa: BLE001 - never break authentication on cache outage
            self._on_backend_error(exc)

    async def _hit(self, base_key: str, limit: int) -> None:
        count_key = f"{base_key}:count"
        count = await self.backend.incr(
            count_key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
        )
        if count < limit:
            return
        strikes_key = f"{base_key}:strikes"
        strikes = int(await self.backend.get(strikes_key) or 0) + 1
        await self.backend.set(
            strikes_key, str(strikes), settings.LOGIN_RATE_LIMIT_STRIKES_TTL_SECONDS
        )
        block_seconds = min(
            settings.LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS * (2 ** (strikes - 1)),
            settings.LOGIN_RATE_LIMIT_MAX_BLOCK_SECONDS,
        )
        await self.backend.set(f"{base_key}:block", "1", block_seconds)
        await self.backend.delete(count_key)

    async def record_success(self, *, ip: str, account_hash: str) -> None:
        try:
            account = self.account_key(account_hash)
            address = self.ip_key(ip)
            await self.backend.delete(
                f"{account}:count",
                f"{account}:strikes",
                f"{address}:count",
            )
        except Exception as exc:  # noqa: BLE001
            self._on_backend_error(exc)

    def reset_local(self) -> None:
        self.backend.reset_local()

    async def reset(self) -> None:
        await self.backend.reset()


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


login_limiter = LoginLimiter(_backend())
