"""Tool: search_places — search for attractions, restaurants, and hotels via Amap."""

import json
from enum import Enum
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
import requests

from ..config import settings
from ..amap_client import AmapClient, CATEGORY_CODES


class PlaceType(str, Enum):
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"


class SearchPlacesInput(BaseModel):
    """Input schema for search_places."""

    query: str = Field(..., description="搜索关键词，例如：浅草寺、寿司店、希尔顿")
    place_type: PlaceType = Field(
        default=PlaceType.ATTRACTION,
        description="地点类型：attraction（景点）、restaurant（餐厅）、hotel（酒店）",
    )
    city: Optional[str] = Field(
        default=None,
        description="限定搜索的城市（中文名或 adcode），例如：北京、杭州。不填则全国搜索",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="返回结果数量上限",
    )


_PLACE_TYPE_LABELS: dict[PlaceType, str] = {
    PlaceType.ATTRACTION: "景点",
    PlaceType.RESTAURANT: "餐厅",
    PlaceType.HOTEL: "酒店",
}


@tool(args_schema=SearchPlacesInput)
def search_places(
    query: str,
    place_type: PlaceType = PlaceType.ATTRACTION,
    city: Optional[str] = None,
    limit: int = 5,
) -> str:
    """搜索景点、餐厅或酒店。

    使用高德地图 POI 搜索 API，根据关键词和类型返回匹配的地点列表。
    结果包含名称、地址、评分、人均消费和坐标等信息。
    """
    client = AmapClient()

    type_code = CATEGORY_CODES.get(place_type.value, "")
    data = client.text_search(
        keywords=query,
        types=type_code,
        city=city or "",
        offset=limit,
    )

    if not client.amap_status_ok(data):
        return json.dumps(
            {"error": f"高德 API 返回异常: {data.get('info', 'unknown')}"},
            ensure_ascii=False,
        )

    pois = data.get("pois") or []
    results: list[dict] = []
    for poi in pois[:limit]:
        biz = poi.get("biz_ext") or {}
        results.append({
            "name": poi.get("name", ""),
            "type": _PLACE_TYPE_LABELS.get(place_type, place_type.value),
            "address": poi.get("address", ""),
            "city": poi.get("cityname", ""),
            "district": poi.get("adname", ""),
            "rating": poi.get("biz_ext", {}).get("rating") or None,
            "avg_cost": poi.get("biz_ext", {}).get("cost") or None,
            "telephone": poi.get("tel") or [],
            "location": poi.get("location", ""),
            "distance": poi.get("distance", ""),
        })

    return json.dumps(
        {"query": query, "place_type": place_type.value, "count": len(results), "results": results},
        ensure_ascii=False,
        indent=2,
    )
