import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User, UserToken
from schemas.users import UserRequest
from utils import security


#根据用户名查询数据库
async def get_user_by_username(db: AsyncSession, username:str):
    query = select(User).where(User.username == username)
    result = await db.execute(query)

    return result.scalar_one_or_none()



#创建用户
async def create_user(db: AsyncSession, user_data: UserRequest):
     hashed_password = security.get_hash_password(user_data.password)
     user = User(username=user_data.username, password=hashed_password)
     db.add(user)
     await db.commit()
     await db.refresh(user)

     return user

#生成token
async def create_token(db: AsyncSession, user_id:int):
    token = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7)
    query = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token = token
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(token=token, user_id=user_id,expires_at=expires_at)
        db.add(user_token)
        await db.commit()

    return token

#根据用户名和密码查询用户
async def authenticate_user(db: AsyncSession, username:str, password:str):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not security.verify_password(password, user.password):
        return None
    return user

#根据token查询用户
async def get_user_by_token(db: AsyncSession, token:str):
    query = select(UserToken).where(UserToken.token == token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.expires_at < datetime.now():
        return None

    query = select(User).where(User.id == db_token.user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()
