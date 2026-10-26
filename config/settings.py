"""应用统一配置 — 全项目唯一的设置来源。

新闻后端与旅行助手（travel_agent）共用本模块，任何新增配置项都只在这里声明一次。
从项目根目录的 .env 加载；env_file 用绝对路径，因此无论从哪个工作目录启动
（uvicorn / init_db / 直接 import travel_agent）都能正确读到配置。
"""

import secrets
import warnings
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（config/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """集中管理新闻后端与旅行助手的配置项。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    MYSQL_URL: str = ""

    # JWT 认证
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7

    @model_validator(mode="after")
    def _ensure_jwt_secret(self) -> "Settings":
        """绝不允许用空密钥签名——那等于任何人都能伪造 token。

        未配置时临时生成一个随机密钥，保证「跑起来是安全的」，
        代价是重启后已签发的 token 会失效。生产环境必须在 .env 里设固定值。
        """
        if not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = secrets.token_urlsafe(32)
            warnings.warn(
                "JWT_SECRET_KEY 未在 .env 中配置，已临时生成随机密钥；"
                "服务重启后已签发的 token 将全部失效。请在 .env 中设置固定值。",
                stacklevel=2,
            )
        return self

    # DeepSeek LLM（旅行助手）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 高德地图 Web API
    AMAP_API_KEY: str = ""

    # LangSmith 链路追踪（可选）
    LANGCHAIN_TRACING_V2: str = ""
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "travel-agent"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"


settings = Settings()