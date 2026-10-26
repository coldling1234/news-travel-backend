"""ORM 模型包 —— import 本包即把全部模型注册到 Base.metadata。

init_db.py 依赖这一点：只要 `from models import Base`，所有模型就已注册，
create_all 才能一次建全。新增模型后请在这里补上导入，否则建表时会漏。

已知「数据库中有、但暂无 ORM 模型」的 4 张表：
    ai_chat        AI 对话记录
    favorite       收藏
    history        浏览历史
    related_news   相关新闻
它们目前都是空表，属于规划中但尚未实现的功能。

警告：将来若接入 Alembic，`alembic revision --autogenerate` 会因为
metadata 中找不到这 4 张表而生成 DROP TABLE 语句。生成迁移后务必人工检查
并删掉这些 DROP，或先为它们补上 ORM 模型。
"""

from models.base import Base, TimestampMixin
from models.news import Category, News
from models.users import User, UserToken

__all__ = [
    "Base",
    "TimestampMixin",
    "Category",
    "News",
    "User",
    "UserToken",
]
