"""Tool: get_weather — query weather forecast using Open-Meteo free API."""

import json
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..weather_client import WeatherClient, generate_travel_advice


class GetWeatherInput(BaseModel):
    """Input schema for get_weather."""

    location: str = Field(
        ..., description="城市或地点名称，例如：东京、杭州、纽约"
    )
    days: int = Field(
        default=7, ge=1, le=14, description="预报天数（1-14 天）"
    )


@tool(args_schema=GetWeatherInput)
def get_weather(location: str, days: int = 7) -> str:
    """查询指定地点的天气预报。

    使用 Open-Meteo 免费天气 API（无需 API Key），返回未来若干天的天气状况、
    温度、降水概率、风速、紫外线指数、日出日落时间，以及针对每日的旅行建议。

    Args:
        location: 城市或地点名称。
        days: 预报天数。
    """
    client = WeatherClient()

    try:
        forecast = client.get_weather(location, forecast_days=days)
    except ValueError as e:
        return json.dumps(
            {"error": str(e)},
            ensure_ascii=False,
        )

    # Generate travel advice
    advice_list = generate_travel_advice(forecast)
    for item, tip in zip(forecast, advice_list):
        item["travel_advice"] = tip

    resolved = forecast[0].get("resolved_location", location) if forecast else location

    # Remove internal fields before returning
    clean_forecast: list[dict] = []
    for f in forecast:
        clean = {
            k: v for k, v in f.items()
            if k not in ("weather_code", "resolved_location")
        }
        clean_forecast.append(clean)

    return json.dumps(
        {
            "location": resolved,
            "forecast_days": len(clean_forecast),
            "forecast": clean_forecast,
        },
        ensure_ascii=False,
        indent=2,
    )
