import functools
import hashlib
import json
import os
from typing import Any, Callable

REDIS_URL = os.environ.get("REDIS_URL", "")

_redis = None
try:
    import redis.asyncio as aioredis

    if REDIS_URL:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    _redis = None


async def get_redis():
    return _redis


def _make_key(fn: Callable, args: tuple, kwargs: dict) -> str:
    raw = f"{fn.__module__}:{fn.__qualname__}:{repr(args)}:{repr(sorted(kwargs.items()))}"
    return f"cache:{hashlib.md5(raw.encode()).hexdigest()}"


def cached(ttl: int = 300):
    def decorator(fn):
        is_async = __import__("asyncio").iscoroutinefunction(fn)

        if is_async:

            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                if _redis is None:
                    return await fn(*args, **kwargs)
                key = _make_key(fn, args, kwargs)
                try:
                    cached = await _redis.get(key)
                    if cached is not None:
                        return json.loads(cached)
                except Exception:
                    pass
                result = await fn(*args, **kwargs)
                try:
                    await _redis.setex(key, ttl, json.dumps(result, default=str))
                except Exception:
                    pass
                return result

        else:

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if _redis is None:
                    return fn(*args, **kwargs)
                key = _make_key(fn, args, kwargs)
                try:
                    import asyncio

                    loop = asyncio.new_event_loop()
                    cached = loop.run_until_complete(_redis.get(key))
                    loop.close()
                    if cached is not None:
                        return json.loads(cached)
                except Exception:
                    pass
                result = fn(*args, **kwargs)
                try:
                    import asyncio

                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(_redis.setex(key, ttl, json.dumps(result, default=str)))
                    loop.close()
                except Exception:
                    pass
                return result

        return wrapper

    return decorator


def invalidate(pattern: str):
    if _redis is None:
        return
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        keys = loop.run_until_complete(_redis.keys(pattern))
        if keys:
            loop.run_until_complete(_redis.delete(*keys))
        loop.close()
    except Exception:
        pass
