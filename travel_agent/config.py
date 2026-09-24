"""应用全局配置 — 从 .env 加载所有 API 密钥和模型参数。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API 配置类，所有敏感密钥和端点统一管理。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek LLM
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


# 全局单例
settings = Settings()
