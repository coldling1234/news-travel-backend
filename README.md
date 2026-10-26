# toutiao_backend

基于 FastAPI 的后端服务，包含**两个相互独立的子系统**：

| 子系统 | 位置 | 说明 |
| --- | --- | --- |
| 新闻内容 API | `routers/news.py`、`routers/users.py` | 新闻分类/列表/详情 + 用户注册登录，SQLAlchemy 异步 ORM + MySQL |
| 旅行规划 Agent | `travel_agent/` | LangGraph ReAct 智能体，DeepSeek 大模型 + 高德地图 + Open-Meteo 天气，9 个工具，输出可解释的旅行计划 |

两者仅共用 `main.py` 挂载，无业务耦合。

> 注：项目名沿用 `toutiao`，但当前代码中新闻部分只提供通用内容接口，未包含推荐/频道等头条特有逻辑。

---

## 快速开始

### 1. 环境准备

Python 版本建议 3.11+。

> ⚠️ **项目根目录下的 `venv/` 是空壳**（`Lib/site-packages/` 下只有 pip），不要用它。
> 它和 `requirements.txt` 没有任何关系，可以直接无视或删除。

推荐两种方式：

```bash
# 方式一：使用已配好的 conda 环境（本项目开发所用）
# PyCharm 解释器配置见 .idea/misc.xml：langchain_313
E:/conda3/envs/langchain_313/python.exe -m uvicorn main:app --reload

# 方式二：新建虚拟环境
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
```

`requirements.txt` 共 17 条，均为**精确锁定的版本号**（按实际可运行环境导出）。
其中 `bcrypt` 锁在 `3.2.0`——`passlib 1.7.4` 与 `bcrypt >= 4.1` 存在兼容问题，不要升级。

### 2. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`。**必填项**：

```ini
MYSQL_URL=mysql+aiomysql://root:1234@localhost:3306/news_app?charset=utf8mb4
JWT_SECRET_KEY=<必填，见下方说明>
AMAP_API_KEY=<旅行助手必需>
DEEPSEEK_API_KEY=<旅行助手必需>
```

`JWT_SECRET_KEY` 生成方式：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **如果不配置 `JWT_SECRET_KEY`，服务每次启动都会随机生成一个**并在启动时打印警告。
> 后果是**每次重启都会把所有已登录用户踢下线**。生产环境务必配置固定值。

完整配置项见本文末尾的[环境变量](#环境变量)一节。

### 3. 初始化数据库

需先确保 MySQL 已启动，且 `MYSQL_URL` 指向的库已创建（脚本不会建库）：

```sql
CREATE DATABASE news_app CHARACTER SET utf8mb4;
```

然后：

```bash
python init_db.py
```

脚本会对比 ORM 定义与数据库现状，**只创建缺失的表**（`checkfirst=True`），
不执行任何 `DROP` 或 `ALTER`，可以放心对已有数据的库运行。

```
[跳过] news  已存在，未做任何修改
...
所有表均已存在，无需创建。
```

### 4. 启动服务

```bash
python -m uvicorn main:app --reload --port 8000
```

启动后访问：

- Swagger 交互文档：<http://127.0.0.1:8000/docs>
- ReDoc：<http://127.0.0.1:8000/redoc>
- 健康检查：<http://127.0.0.1:8000/api/travel/health>

---

## 项目结构

```
toutiao_backend/
├── main.py                  # FastAPI 入口，挂载三个路由 + CORS
├── init_db.py               # 建表脚本（只补建，不删不改）
├── requirements.txt
├── .env.example             # 环境变量模板
│
├── config/
│   ├── settings.py          # 【唯一配置源】全项目共用
│   └── db_conf.py           # 异步引擎 / 会话工厂 / get_db 依赖
│
├── models/                  # SQLAlchemy ORM
│   ├── base.py              # 唯一 Base + TimestampMixin
│   ├── news.py              # Category、News
│   └── users.py             # User、UserToken
├── crud/                    # 数据库操作层
├── schemas/                 # Pydantic 请求模型
├── routers/                 # HTTP 路由层
│   ├── news.py  users.py  travel.py
└── utils/
    ├── security.py          # 密码哈希(bcrypt) + JWT 签发/校验
    └── auth.py              # FastAPI 认证依赖
│
└── travel_agent/            # 旅行规划 Agent
    ├── agent.py             # LangGraph ReAct 智能体组装
    ├── pipeline.py          # 偏好提取 + 摘要流水线
    ├── extractor.py         # 自然语言 → 结构化偏好（三层降级解析）
    ├── summarizer.py        # 约束摘要
    ├── planner.py           # 行程生成（多分支 prompt）
    ├── scorer.py            # 可解释评分：酒店 / 路线
    ├── profile.py           # 用户画像 → 动态评分权重
    ├── history.py           # 历史偏好（⚠️ 当前未被调用）
    ├── amap_client.py       # 高德地图 API（重试 + 指数退避）
    ├── weather_client.py    # Open-Meteo 天气（无需 Key）
    ├── pii_masking.py       # LLM 调用前的 PII 脱敏回调
    └── tools/               # 9 个 @tool
```

---

## API 接口

统一响应格式：`{ "code": 200, "message": "...", "data": {...} }`。

> 注意：由 `HTTPException` 抛出的错误（如 401/404/400）使用 FastAPI 默认格式
> `{ "detail": "..." }`，不走上面的包装格式。

### 新闻 `/api/news`

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| GET | `/categories` | `skip=0` `limit=100` | 分类列表 |
| GET | `/list` | **`categoryId`**(必填) `page=1` `pageSize=10`(≤100) | 新闻列表，返回 `list/total/hasMore` |
| GET | `/detail` | **`id`**(必填) | 新闻详情，**每次访问自动 +1 浏览量**，并附带相关新闻 |

```bash
curl "http://127.0.0.1:8000/api/news/list?categoryId=1&page=1&pageSize=10"
curl "http://127.0.0.1:8000/api/news/detail?id=1"
```

> 参数名是 `categoryId` / `pageSize`（驼峰，通过 `alias` 映射），
> 写成 `category_id` / `page_size` 会返回 422。

### 用户 `/api/user`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/register` | 否 | 注册，直接返回 token；用户名重复返回 400 |
| POST | `/login` | 否 | 登录，返回 token；账号密码错误返回 400 |
| GET | `/info` | **是** | 当前用户信息 |

请求体：`{ "username": "...", "password": "..." }`

认证方式：`Authorization: Bearer <token>`（JWT，HS256，默认 7 天有效）。

```bash
# 注册
curl -X POST http://127.0.0.1:8000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# 访问受保护接口
curl http://127.0.0.1:8000/api/user/info \
  -H "Authorization: Bearer <上一步返回的 token>"
```

JWT 自验证不查库。无头 / 格式错误 / 签名篡改 / 过期，均返回 401。

### 旅行助手 `/api/travel`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查，不依赖外部服务 |
| POST | `/chat` | 多轮对话式旅行规划 |

请求体：

```json
{ "sessionId": "可选，不传则服务端新建", "message": "我想去成都玩三天，预算3000" }
```

响应：`{ "code": 200, "data": { "sessionId": "...", "reply": "..." } }`

```bash
curl -X POST http://127.0.0.1:8000/api/travel/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"我想去成都玩三天，预算3000，喜欢安静"}'
```

多轮对话靠 `sessionId` 串联，服务端**在内存中保存上下文**。
不传 `sessionId` 时服务端会自动生成一个并在响应中返回，后续请求带上它即可延续对话。

> ⚠️ **客户端不要只看 HTTP 状态码。** 该接口出错时返回的是 `200` + body 里
> `"code": 500`（消息为空则是 `"code": 400`），与其他接口的 `HTTPException` 行为不同。
> 判断成功与否请检查 body 中的 `code` 字段。

> ⚠️ 该接口是**同步阻塞**的，一次 LLM 往返可能耗时几十秒，
> 期间会卡住整个 event loop（包括新闻接口）。详见[已知问题](#已知问题与待办)。

### 根路径

`GET /` 和 `GET /hello/{name}` 为脚手架自带的示例接口。

---

## 数据模型

ORM 管理的 4 张表（统一 `Base` 定义在 `models/base.py`）：

| 表 | 说明 | 主要字段 |
| --- | --- | --- |
| `news_category` | 新闻分类 | `id` `name` `sort_order` |
| `news` | 新闻正文 | `id` `title` `description` `content` `image` `author` `category_id`(FK) `views` `publish_time` |
| `user` | 用户 | `id` `username`(唯一) `password`(bcrypt) `nickname` `avatar` `gender` `bio` `phone`(唯一) |
| `user_token` | 令牌 | `id` `user_id`(FK) `token`(唯一) `expires_at` |

`created_at` / `updated_at` 由 `TimestampMixin` 统一提供
（`user_token` 表无 `updated_at`，故未继承 mixin）。

> **`user_token` 表目前不再参与认证**。改为 JWT 后 token 不再落库，
> 该表仅保留历史数据，将来做刷新令牌或主动登出时可复用。

数据库中另有 4 张**空表且无 ORM 模型**：`ai_chat`、`favorite`、`history`、`related_news`
（规划中的 AI 对话、收藏、浏览历史、相关推荐）。
将来若接入 Alembic，autogenerate 会生成 `DROP TABLE` 误删它们，需人工拦截——
`models/__init__.py` 的注释中已标注。

---

## 旅行助手工作原理

```
用户输入
   │
   ▼
collect_preferences ──► 自然语言 → 结构化 TravelPreference
   │                      └─► profile.py 更新用户画像（影响后续评分权重）
   ▼
search_places / geocode_location ──► 高德地图 POI 与地理编码
   │
   ├──► score_hotels   按 评分/口碑、位置、安静度 加权排序
   ├──► score_routes   按 耗时、距离、换乘、费用 加权排序
   ├──► estimate_route 路径规划（驾车/公交/步行/骑行）
   ├──► get_weather    Open-Meteo 天气预报（无需 Key）
   └──► estimate_budget 花费区间估算
   │
   ▼
plan_trip ──► 生成 Markdown 行程（约束摘要 + 总览 + 每日计划 + 预算拆分 + 风险备选）
```

9 个工具均为 `@tool` 装饰的 LangChain 工具，由 `create_react_agent` 自主选择调用。

**可解释评分**是这一模块的设计亮点：`scorer.py` 对候选酒店/路线做 min-max 归一化打分，
并输出每个维度的得分与理由，而非黑盒排序；权重会根据 `profile.py` 中
从用户偏好抽取的标签（安静 / 省钱 / 省时 / 少换乘）动态调整。

---

## 环境变量

全部在 `config/settings.py` 中声明——**这是全项目唯一的配置来源**，
新增配置项只在这里加一次，不要在子模块另建 Settings 类。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MYSQL_URL` | 空 | MySQL 异步连接串，需 `mysql+aiomysql://` |
| `JWT_SECRET_KEY` | 空 | **必填**。留空则每次启动随机生成 |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `JWT_EXPIRE_DAYS` | `7` | token 有效期（天） |
| `DEEPSEEK_API_KEY` | 空 | 旅行助手必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | |
| `DEEPSEEK_MODEL` | `deepseek-chat` | |
| `AMAP_API_KEY` | 空 | 旅行助手必需，[申请地址](https://lbs.amap.com/api/webservice/create-project) |
| `LANGCHAIN_TRACING_V2` | 空 | 设为 `true` 启用 LangSmith 追踪 |
| `LANGCHAIN_API_KEY` | 空 | LangSmith Key，可选 |
| `LANGCHAIN_PROJECT` | `travel-agent` | |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | |

`env_file` 使用**绝对路径**（基于 `config/` 的上一级目录），
因此从任意工作目录启动都能正确读到 `.env`。

---

## 已知问题与待办

按影响程度排序：

1. **`plan_trip` 未接入天气与历史偏好**。`history.py` 的 `save_preference()` /
   `build_history_context()` 目前是**死代码**，全项目无调用点，
   导致 planner 中"参考历史偏好"的 prompt 从未生效。
2. **`/api/travel/chat` 同步阻塞 event loop**。应使用 `async def` + 线程池或 `ainvoke`。
3. **会话存储在内存 dict**。重启即丢失、多 worker 下失效、无过期清理，
   消息列表也会无限增长。
4. **PII 脱敏未闭环**。`PIIMaskingHandler` 只挂在 `agent.py` 一个 LLM 实例上，
   `extractor` / `planner` / `scorer` 各自创建的 LLM 均未挂载；且只脱敏不还原。
5. **CORS 配置不安全**：`allow_origins=["*"]` 配合 `allow_credentials=True`
   会被浏览器拒绝，生产环境需改为指定源。
6. **数据库层差异**（新环境才会暴露）：`user_token` 外键生产库为 `ON DELETE CASCADE`
   但 ORM 未声明；`news_category` 唯一索引名不一致；`news.publish_time` 索引方向不一致。
7. **无测试、无 Dockerfile、无日志与全局异常处理**；
   `config/db_conf.py` 的 `echo=True` 会把所有 SQL 打到日志。

---

## 开发注意事项

- **不要 DROP 生产库的索引**。`user` / `user_token` 上的 `username_UNIQUE` /
  `phone_UNIQUE` / `token_UNIQUE` 本身就是唯一约束（`Non_unique=0`），删掉会直接丢失唯一性。
- **改动依赖后同步 `requirements.txt`**，版本号应从真实环境导出，不要手写。
- **数据库有真实数据**（`news` 400+ 行），任何脚本都不得执行 `DROP`。
- 配置相关的改动请只改 `config/settings.py`，其他地方一律从它 import。
