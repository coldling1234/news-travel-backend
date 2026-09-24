"""Tool: score_hotels — 对候选酒店进行多维加权评分并排序。"""

import json
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..scorer import HotelScorer, HotelCandidate
from ..profile import load_profile, compute_hotel_weights


class ScoreHotelsInput(BaseModel):
    """Input schema for score_hotels."""
    hotels_json: str = Field(
        ...,
        description="search_places 返回的 JSON 字符串，需包含 results 数组",
    )
    reference: Optional[str] = Field(
        default=None,
        description="目的地或参考点坐标 lng,lat，用于位置便利性评分",
    )


def _num(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@tool(args_schema=ScoreHotelsInput)
def score_hotels(hotels_json: str, reference: Optional[str] = None) -> str:
    """对候选酒店按评分/口碑、位置便利性、安静度进行加权评分并排序。"""
    data = json.loads(hotels_json)
    raw = data.get("results") if isinstance(data, dict) else data

    candidates: list[HotelCandidate] = []
    for item in raw or []:
        candidates.append(HotelCandidate(
            name=item.get("name", ""),
            rating=_num(item.get("rating")),
            cost=_num(item.get("avg_cost")),
            location=item.get("location") or None,
            distance=_num(item.get("distance")),
            address=item.get("address", ""),
            place_type=item.get("type", ""),
        ))

    if not candidates:
        return json.dumps({"error": "没有可评分的酒店候选"}, ensure_ascii=False)

    profile = load_profile()
    weights = compute_hotel_weights(profile)
    scored = HotelScorer().score(candidates, weights=weights, reference=reference)

    return json.dumps(
        {
            "weights": weights,
            "profile_tags": profile.tags,
            "results": [item.model_dump() for item in scored],
        },
        ensure_ascii=False,
        indent=2,
    )
