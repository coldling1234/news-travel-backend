from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
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

#根据ID查询用户（JWT 验签拿到 user_id 后，用它换取用户对象）
async def get_user_by_id(db: AsyncSession, user_id:int):
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)

    return result.scalar_one_or_none()

#根据用户名和密码查询用户
async def authenticate_user(db: AsyncSession, username:str, password:str):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not security.verify_password(password, user.password):
        return None
    return user

# 注：认证已改用 JWT（见 utils/security.py 的 create_access_token），
# 不再往 user_token 表写 uuid token，因此这里没有 create_token / get_user_by_token。
# user_token 表保留：里面还有旧数据，且将来要做刷新令牌或主动登出时可复用。
