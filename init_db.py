"""建表脚本 —— 只补建缺失的表，绝不删除或改动已有的表和数据。

用法：

    python init_db.py

做了什么：

    1. 读取 .env 里的 MYSQL_URL 连接数据库
    2. 对比 Base.metadata 中声明的表 与 数据库中已存在的表
    3. 只创建缺失的表；已存在的表原样跳过，一个字节都不动
    4. 打印一份报告

不会做什么（重要）：

    - 不 DROP 任何表，不删除任何数据
    - 不做 ALTER。改了模型字段（加列 / 改类型）后已存在的表不会被更新，
      那种情况需要 Alembic 迁移；本脚本只负责「让新环境把表建出来」
"""

import asyncio
import sys

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import settings
from models import Base  # 导入即注册全部模型


async def main() -> int:
    if not settings.MYSQL_URL:
        print("错误：.env 中未配置 MYSQL_URL")
        return 1

    engine = create_async_engine(settings.MYSQL_URL, echo=False)

    try:
        async with engine.connect() as conn:
            existing = set(
                await conn.run_sync(lambda c: inspect(c).get_table_names())
            )
    except Exception as exc:
        print(f"错误：无法连接数据库 -> {exc}")
        print("请确认 MySQL 已启动，且 MYSQL_URL 指向的库（如 news_app）已经创建")
        await engine.dispose()
        return 1

    wanted = set(Base.metadata.tables.keys())
    already = sorted(wanted & existing)
    missing = sorted(wanted - existing)

    print(f"数据库已存在的表：{len(existing)} 张")
    print(f"ORM 声明的表：    {len(wanted)} 张")
    print()

    for name in already:
        print(f"  [跳过] {name}  已存在，未做任何修改")

    if not missing:
        print("\n所有表均已存在，无需创建。")
    else:
        print(f"\n将创建 {len(missing)} 张表：{', '.join(missing)}")
        tables = [Base.metadata.tables[name] for name in missing]
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda c: Base.metadata.create_all(c, tables=tables, checkfirst=True)
            )
        for name in missing:
            print(f"  [已创建] {name}")

    await engine.dispose()
    print("\n完成。本脚本只创建缺失的表，未删除或改动任何已有的表和数据。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
