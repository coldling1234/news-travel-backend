"""认证依赖 — 从 Authorization 头取 JWT，验签后换取当前用户。"""

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from crud import users
from models.users import User
from utils.security import decode_access_token

# auto_error=False：缺少或格式不对的 Authorization 头由我们自己返回 401，
# 而不是让 HTTPBearer 直接抛 403，这样错误信息更可控。
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析并校验 JWT，返回对应的用户对象。

    两处容易踩的坑，这里都避开了：
    1. Depends(get_db) 不能写成 Depends(get_db())——后者会在导入时就把异步
       生成器调用掉，拿到一个不可调用的对象，FastAPI 解析依赖时直接报错。
    2. 查询结果必须接住再用。旧代码里 `await users.get_user_by_token(...)`
       的返回值被丢弃，导致后续判断的是一个恒为真的对象，认证形同虚设。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌",
            headers=_UNAUTHORIZED_HEADERS,
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌或已过期的令牌",
            headers=_UNAUTHORIZED_HEADERS,
        )

    user = await users.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已注销",
            headers=_UNAUTHORIZED_HEADERS,
        )

    return user