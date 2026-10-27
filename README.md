# toutiao_backend

FastAPI 后端 + Vue 3 前端，包含新闻内容接口、用户系统，以及基于 LangGraph 的旅行规划 Agent。

---

## 环境要求

| | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.11+ | 后端 |
| MySQL | 5.7+ / 8.0 | 需先创建数据库 |
| Node.js | 20.19+ 或 22.12+ | 前端（Vite 7 要求） |

> ⚠️ **项目根目录的 `venv/` 是空壳**（只有 pip），不要用它，可直接删除。

---

## 启动后端

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，**必填项**：

```ini
MYSQL_URL=mysql+aiomysql://root:1234@localhost:3306/news_app?charset=utf8mb4
JWT_SECRET_KEY=<用下面命令生成>
AMAP_API_KEY=<旅行助手必需>
DEEPSEEK_API_KEY=<旅行助手必需>
```

`JWT_SECRET_KEY` 生成：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> 不配置的话服务每次启动会随机生成并告警，**后果是每次重启都把已登录用户踢下线**。

### 3. 创建数据库并建表

脚本不会建库，先在 MySQL 里执行：

```sql
CREATE DATABASE news_app CHARACTER SET utf8mb4;
```

然后：

```bash
python init_db.py
```

只创建缺失的表，**不 DROP、不 ALTER**，对有数据的库可以放心运行。

### 4. 启动服务

```bash
python -m uvicorn main:app --reload --port 8000
```

---

## 启动前端

```bash
cd xwzx-news
npm install
npm run dev
```

---

## 访问地址

| 服务 | 地址 |
| --- | --- |
| 前端页面 | <http://localhost:5173> |
| 后端接口 | <http://127.0.0.1:8000> |
| Swagger 接口文档 | <http://127.0.0.1:8000/docs> |

前端通过 `src/config/api.js` 里的 `baseURL` 直连后端 `127.0.0.1:8000`（后端已开 CORS）。
若后端换了端口，需同步修改该文件。

> 端口被占用时 Vite 会自动顺延（如 5173→5174），以终端输出为准。

---

## 环境变量

配置统一在 `config/settings.py` 声明，其他地方一律从它导入。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MYSQL_URL` | 空 | MySQL 异步连接串 |
| `JWT_SECRET_KEY` | 空 | **必填**，JWT 签名密钥 |
| `JWT_ALGORITHM` | `HS256` | 签名算法 |
| `JWT_EXPIRE_DAYS` | `7` | token 有效期（天） |
| `DEEPSEEK_API_KEY` | 空 | 旅行助手必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | |
| `DEEPSEEK_MODEL` | `deepseek-chat` | |
| `AMAP_API_KEY` | 空 | 旅行助手必需 |
| `LANGCHAIN_TRACING_V2` | 空 | 设为 `true` 启用 LangSmith |
| `LANGCHAIN_API_KEY` | 空 | 可选 |
| `LANGCHAIN_PROJECT` | `travel-agent` | |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | |

---

## 注意事项

- **不要 DROP 生产库索引**：`user` / `user_token` 上的 `username_UNIQUE` / `phone_UNIQUE` /
  `token_UNIQUE` 本身就是唯一约束，删掉会直接丢失唯一性。
- **数据库有真实数据**（`news` 400+ 行），任何脚本都不得执行 `DROP`。
- `/api/user/*` 与 `/api/travel/*` 下**仍有部分接口后端未实现**（收藏、浏览历史、
  修改资料、修改密码），前端调用会返回 404。
- `/api/travel/chat` 是同步阻塞的，单次请求可能耗时几十秒；出错时返回
  **HTTP 200 + body 内 `"code": 500`**，判断成败要看 body 里的 `code`。
- CORS 当前为 `allow_origins=["*"]`，生产环境需改为指定源。
