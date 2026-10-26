"""统一 declarative 基类与公共字段 mixin。

背景：此前 models/news.py 与 models/users.py 各自定义了一个
DeclarativeBase，两个 metadata 互不相通，导致 create_all 只能建出
一半的表（建 news 就漏掉 user，反之亦然）。全项目现在只保留这一个 Base。
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """全项目唯一的 declarative 基类，所有 ORM 模型都必须继承它。"""

    pass


class TimestampMixin:
    """创建时间 / 更新时间公共字段。

    只对确实有这两个字段的表使用。注意 user_token 表没有 updated_at，
    因此 UserToken 不继承本 mixin，而是自己单独声明 created_at。

    default 必须传函数对象 datetime.now，不能写成 datetime.now()——
    后者在模块导入时就求值一次，会让所有行共用同一个固定时间戳，
    且 onupdate 会永久失效。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
