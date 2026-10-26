# 项目长期记忆 · toutiao_backend

## 运行环境（重要）
- **真实解释器不是项目内的 `venv/`** —— 那个 venv 是空壳，`Lib/site-packages/` 下只有 pip。
- PyCharm 实际配置的是 conda 环境 **`langchain_313`**，路径 `E:\conda3\envs\langchain_313`
  （见 `.idea/misc.xml` 的 `ProjectRootManager project-jdk-name="langchain_313"`）。
- 验证命令用：`/e/conda3/envs/langchain_313/python.exe`
- MySQL 确实在 3306 监听，数据库是真实可用的。

## requirements.txt — 已于 2026-10-26 重建（现在可信）
由真实环境导出精确版本 + AST 扫描过滤，17 条，已验证格式合法且版本逐条一致。
**维护约定**：改动依赖后若环境变动，需重新导出同步，别手写版本号。
bcrypt 锁 3.2.0（passlib 1.7.4 与 bcrypt>=4.1 不兼容）。

## 为什么"看起来能跑"（2026-10-26 实测结论）
三个问题都被"代码路径没走到"掩盖，不是代码正确：
1. `utils/auth.py` 唯一使用者 `/api/user/info` 被注释 → 依赖从未被 FastAPI 解析。
   实测取消注释后**路由注册阶段即崩**：
   `TypeError: <async_generator object get_db ...> is not a callable object`（`Depends(get_db())` 多括号）。
2. `from sqlalchemy.sql.functions import user` 是 SQL 函数类，`bool()` 恒 True →
   `if not user` 永不成立。**即使修好第 1 点，认证仍静默失效且不报错**（最危险）。
3. 两个 DeclarativeBase 无建表代码，但现有 MySQL 表已手动建好 → 换机器才暴露。

## 已完成修复
- **requirements.txt**：2026-10-26 按真实环境重建，17 条精确版本。
- **统一 Base + 建表脚本**：2026-10-26 完成。`models/base.py` 是唯一 Base +
  TimestampMixin；`python init_db.py` 只补建缺失表，不 DROP 不 ALTER。
  数据库 `news_app` 有真实数据（news=403 / user=5 / token=2 / category=8），
  **任何操作都禁止 DROP**。

## 已完成修复（第 3 项）
- **认证已改为 JWT**（PyJWT 2.15.1，HS256）。`utils/security.py` 提供
  `create_access_token` / `decode_access_token`；`utils/auth.py` 用
  `HTTPBearer(auto_error=False)`；`/api/user/info` 已恢复。
- **必须在 .env 配置 JWT_SECRET_KEY**，否则每次重启随机生成 → 已签发 token 全部失效。
- 旧 uuid token 已全部失效，user_token 表保留但不再用于认证。

## 已完成修复（第 4 项 · 合并 Settings）
- **配置唯一来源 = `config/settings.py`**。`travel_agent/config.py` 已删除（git 可恢复）。
  7 个文件改为 `from config.settings import settings`：agent / amap_client / extractor /
  planner / scorer / tools.estimate_budget / tools.search_places。
- **`env_file` 改为绝对路径**（`PROJECT_ROOT / ".env"`），因此从任意 cwd 启动
  （uvicorn / init_db / 直接 import travel_agent）都能读到 .env。原相对路径依赖 cwd。
- **约定**：新增配置项只在 config/settings.py 声明一次，不要在子模块另建 Settings。

## 尚未处理
1. .env 尚未配置 JWT_SECRET_KEY（当前每次启动随机生成，会踢下线所有已登录用户）
2. 外键级联：user_token 生产库是 ON DELETE CASCADE，ORM 未声明 → 新环境删用户会残留 token
3. news_category 唯一索引名（生产 name_UNIQUE vs ORM name）、news.publish_time 索引 DESC
4. travel history/weather 未接入 plan_trip（build_history_context 是死代码）
5. travel chat 同步阻塞 event loop；PII 脱敏未挂到全部 LLM 实例

## 索引禁忌（血泪）
生产库 user/user_token 的 `username_UNIQUE` / `phone_UNIQUE` / `token_UNIQUE`
本身就是唯一约束（Non_unique=0），**严禁 DROP**，否则直接丢失唯一性。
冗余只曾存在于 create_all 新建的表里，已于 2026-10-26 通过
`UniqueConstraint(name=...)` + 去掉列级 unique=True 修掉。
