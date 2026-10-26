from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext

from config.settings import settings

#创建密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#密码加密
def get_hash_password(password):
    return pwd_context.hash(password)

#验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT 令牌
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """签发一个 JWT，payload 里只放用户 ID 和过期时间。

    token 自带签名，校验时不查库——这也是换掉原来 uuid 明文 token 的原因。
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.JWT_EXPIRE_DAYS))
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """验签并解析出 user_id。

    签名不对、已过期、格式错误一律返回 None，由调用方决定怎么响应，
    这样不会把具体原因（比如「过期」）泄露给客户端。
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except PyJWTError:
        return None

    subject = payload.get("sub")
    if not subject:
        return None
    try:
        return int(subject)
    except (TypeError, ValueError):
        return None