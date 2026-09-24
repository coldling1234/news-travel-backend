"""Tool: geocode_location — convert place names to coordinates via Amap.

Handles disambiguation when a place name matches multiple locations.
"""

import json
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..amap_client import AmapClient


class GeocodeInput(BaseModel):
    """Input schema for geocode_location."""

    place_name: str = Field(..., description="要查询的地点名称，例如：南山、中山公园、鼓楼")
    city: Optional[str] = Field(
        default=None,
        description="限定城市范围（中文名），用于消歧。例如指定 city=深圳 来区分深圳南山与重庆南山",
    )


@tool(args_schema=GeocodeInput)
def geocode_location(
    place_name: str,
    city: Optional[str] = None,
) -> str:
    """将地名转换为经纬度坐标。

    使用高德地图地理编码 API。当存在同名地点（如全国多个"鼓楼"）时，
    返回所有候选结果，按城市/区县分组，方便进一步消歧。
    """
    client = AmapClient()

    data = client.geocode(address=place_name, city=city)
    if not client.amap_status_ok(data):
        return json.dumps(
            {"error": f"高德 API 返回异常: {data.get('info', 'unknown')}"},
            ensure_ascii=False,
        )

    geocodes = data.get("geocodes") or []
    if not geocodes:
        return json.dumps(
            {
                "place_name": place_name,
                "city_filter": city,
                "warning": "未找到匹配的坐标，请检查地名拼写或尝试更具体的名称",
                "candidates": [],
            },
            ensure_ascii=False,
            indent=2,
        )

    # If city filter was provided and gave exactly 1 result, return it directly
    if city and len(geocodes) == 1:
        g = geocodes[0]
        return json.dumps(
            {
                "place_name": place_name,
                "city_filter": city,
                "matched": {
                    "formatted_address": g.get("formatted_address", ""),
                    "province": g.get("province", ""),
                    "city": g.get("city", ""),
                    "district": g.get("district", ""),
                    "location": g.get("location", ""),
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    # Multiple candidates → return all with disambiguation info
    candidates: list[dict] = []
    for g in geocodes:
        candidates.append({
            "formatted_address": g.get("formatted_address", ""),
            "province": g.get("province", ""),
            "city": g.get("city", ""),
            "district": g.get("district", ""),
            "location": g.get("location", ""),
            "level": g.get("level", ""),
        })

    result: dict = {
        "place_name": place_name,
        "city_filter": city,
        "count": len(candidates),
        "candidates": candidates,
    }

    if len(candidates) > 1:
        result["disambiguation_hint"] = (
            f"'{place_name}' 匹配到 {len(candidates)} 个可能的地点。"
            "请根据 province/city/district 列选择正确的候选位置。"
            "如需精确匹配，请在查询时指定 city 参数。"
        )

    return json.dumps(result, ensure_ascii=False, indent=2)
