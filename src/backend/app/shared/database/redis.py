"""Redis 客户端和 Refresh Token 撤销能力。"""

import hashlib
import json
import uuid
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis, from_url

from app.shared.config.settings import get_settings

settings = get_settings()
redis_client: Redis = from_url(  # type: ignore[no-untyped-call]
    settings.redis_url,
    decode_responses=True,
)

# 每个并发流使用独立租约成员。Lua 在 Redis 服务端完成过期清理、容量判断和加入，
# 避免多个应用实例同时 INCR 时超卖，也避免旧请求结束后误释放新请求的槽位。
ACQUIRE_CHAT_STREAM_SCRIPT = """
local redis_time = redis.call('TIME')
local now_ms = (tonumber(redis_time[1]) * 1000) + math.floor(tonumber(redis_time[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], now_ms + tonumber(ARGV[2]), ARGV[1])
local latest_lease = redis.call('ZRANGE', KEYS[1], -1, -1, 'WITHSCORES')
local key_ttl_ms = math.max(1, math.ceil(tonumber(latest_lease[2]) - now_ms))
redis.call('PEXPIRE', KEYS[1], key_ttl_ms)
return 1
"""

RELEASE_CHAT_STREAM_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
if redis.call('ZCARD', KEYS[1]) == 0 then
    redis.call('DEL', KEYS[1])
end
return 1
"""


async def revoke_refresh_token(jti: str, expires_in_seconds: int) -> None:
    """将 Refresh Token 的 JTI 加入 Redis 黑名单，TTL 不超过 Token 剩余寿命。"""
    await redis_client.setex(f"auth:revoked-refresh:{jti}", expires_in_seconds, "1")


async def is_refresh_token_revoked(jti: str) -> bool:
    """查询 Refresh Token 是否已被撤销。"""
    return bool(await redis_client.exists(f"auth:revoked-refresh:{jti}"))


async def consume_login_attempt(client_key: str, limit: int, window_seconds: int) -> bool:
    """原子记录登录尝试；返回 False 表示当前窗口已达到限额。"""
    key = f"auth:login-rate:{client_key}"
    attempts = await redis_client.incr(key)
    if attempts == 1:
        await redis_client.expire(key, window_seconds)
    return int(attempts) <= limit


async def consume_chat_query(
    user_id: uuid.UUID,
    client_ip: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """同时限制用户和来源 IP；Redis 键不保存明文 IP。"""
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:24]
    keys = [f"chat:rate:user:{user_id}", f"chat:rate:ip:{ip_hash}"]
    accepted = True
    for key in keys:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
        accepted = accepted and int(count) <= limit
    return accepted


async def acquire_chat_stream(user_id: uuid.UUID, limit: int, lease_seconds: int) -> str | None:
    """原子申请单用户 SSE 租约，返回的令牌必须由同一请求释放。

    租约使用 v2 键与历史计数器隔离，避免滚动发布期间 Redis 类型冲突。
    异常退出由租约分值和键 TTL 双重回收；正常结束只删除当前令牌。
    """
    if lease_seconds <= 0:
        raise ValueError("SSE 并发租约时长必须大于 0")
    key = f"chat:concurrency:v2:{user_id}"
    lease_token = uuid.uuid4().hex
    lease_milliseconds = lease_seconds * 1000
    acquired = await cast(
        Awaitable[int | str],
        redis_client.eval(
            ACQUIRE_CHAT_STREAM_SCRIPT,
            1,
            key,
            lease_token,
            str(lease_milliseconds),
            str(limit),
        ),
    )
    return lease_token if int(acquired) == 1 else None


async def release_chat_stream(user_id: uuid.UUID, lease_token: str) -> None:
    """只释放当前请求持有的 SSE 租约，旧请求不能影响后续新租约。"""
    key = f"chat:concurrency:v2:{user_id}"
    await cast(
        Awaitable[object],
        redis_client.eval(RELEASE_CHAT_STREAM_SCRIPT, 1, key, lease_token),
    )


def _tiktok_oauth_state_key(state: str) -> str:
    """将 OAuth state 哈希后用作 Redis 键，避免 Redis 诊断泄露可用 state。"""
    digest = hashlib.sha256(state.encode()).hexdigest()
    return f"oauth:tiktok:state:{digest}"


async def save_tiktok_oauth_state(state: str, payload: dict[str, str], ttl_seconds: int) -> bool:
    """保存一次性 TikTok OAuth state，碰撞时拒绝覆盖。"""
    result = await redis_client.set(
        _tiktok_oauth_state_key(state),
        json.dumps(payload, separators=(",", ":")),
        ex=ttl_seconds,
        nx=True,
    )
    return bool(result)


async def consume_tiktok_oauth_state(state: str) -> dict[str, str] | None:
    """使用 Redis GETDEL 原子消费 state，重复回调不能二次交换 Token。"""
    raw = await redis_client.getdel(_tiktok_oauth_state_key(state))
    if raw is None:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
    ):
        return None
    return parsed
