from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """
    用户信息表
    ORM 模型
    """

    __tablename__ = "user"

    # 唯一约束用命名 UniqueConstraint 表达，而不是列级 unique=True：
    # 列级 unique=True 会让 SQLAlchemy 额外生成一个以列名命名的唯一索引，
    # 与下面这个重名索引并存，白白多出一份冗余索引。
    # 命名保持 username_UNIQUE / phone_UNIQUE，与现有库完全一致。
    __table_args__ = (
        UniqueConstraint("username", name="username_UNIQUE"),
        UniqueConstraint("phone", name="phone_UNIQUE"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="用户ID",
    )
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="用户名",
    )
    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码（加密存储）",
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="昵称",
    )
    avatar: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="头像URL",
        default="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg",
    )
    gender: Mapped[Optional[str]] = mapped_column(
        Enum("male", "female", "unknown"),
        comment="性别",
        default="unknown",
    )
    bio: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="个人简介",
        default="这个人很懒，什么都没留下",
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        comment="手机号",
    )
    # created_at / updated_at 由 TimestampMixin 提供。
    # 原先此处写的是 default=datetime.now()（带括号），会在模块导入时求值一次，
    # 导致所有用户共用同一个时间戳，且 onupdate 永久失效。已修正为 mixin 的写法。

    def __repr__(self):
        return (
            f"<User(id={self.id}, username='{self.username}', "
            f"nickname='{self.nickname}')>"
        )


class UserToken(Base):
    """
    用户令牌表
    ORM 模型
    """

    __tablename__ = "user_token"

    # 创建索引
    __table_args__ = (
        UniqueConstraint("token", name="token_UNIQUE"),
        Index("fk_user_token_user_idx", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="令牌ID",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(User.id),
        nullable=False,
        comment="用户ID",
    )
    token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="令牌值",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="过期时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(),
        comment="创建时间",
    )

    def __repr__(self):
        return f"<UserToken(id={self.id}, user_id={self.user_id}, token='{self.token}')>"

