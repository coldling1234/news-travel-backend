from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from models.users import User
from schemas.users import UserRequest
from crud import users
from utils.auth import get_current_user
from utils.security import create_access_token

router = APIRouter(prefix="/api/user", tags=["users"])


@router.post("/register")
async def register(user_data:UserRequest,db:AsyncSession = Depends(get_db)):

    existing_user = await users.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="用户已存在")
    user = await users.create_user(db, user_data)
    token = create_access_token(user.id)
    return {
        "code": 200,
        "message": "注册成功",
        "data": {
            "token": token,
            "userInfo": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "bio": user.bio
            }
        }
    }

@router.post("/login")
async def login(user_data:UserRequest,db:AsyncSession = Depends(get_db)):

    user = await users.authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="用户名或密码错误")
    token = create_access_token(user.id)
    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": token,
            "userInfo": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "bio": user.bio
            }
        }
    }

@router.get("/info")
async def get_user_info(user:User = Depends(get_current_user)):

    return {
        "code": 200,
        "message": "获取用户信息成功",
        "data": {
            "userInfo": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "bio": user.bio
            }
        }
    }