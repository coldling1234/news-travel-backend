"""应用统一配置 — 从根目录 .env 加载数据库与第三方服务配置。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理新闻后端与旅行助手的配置项。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    MYSQL_URL: str = ""

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