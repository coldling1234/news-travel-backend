from fastapi import Header, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import user
from starlette import status

from config.db_conf import get_db
from crud import users


#整合根据Token查询用户，返回用户
async def get_current_user(
        authorization:str = Header(...,alias="Authorization"),
        db: AsyncSession = Depends(get_db())
):
    #token = authorization.split(" ")[1]
    token = authorization.replace("Bearer ", "")
    await users.get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌或已过期的令牌")

    return user