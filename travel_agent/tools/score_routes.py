"""Tool: score_routes — 对候选路线进行多维加权评分并排序。"""

import json
import re
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..scorer import RouteScorer, RouteCandidate
from ..profile import load_profile, compute_route_weights


class ScoreRoutesInput(BaseModel):
    """Input schema for score_routes."""
    routes_json: str = Field(
        ...,
        description="estimate_route 返回的 JSON 字符串，需包含 routes 数组",
    )


def _parse_cost(item: dict) -> Optional[float]:
    value = item.get("cost")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    estimate = item.get("cost_estimate")
    if isinstance(estimate, str):
        if "免费" in estimate:
            return 0.0
        match = re.search(r"\d+(?:\.\d+)?", estimate)
        if match:
            return float(match.group())
    return None


def _count_transfers(item: dict) -> int:
    segments = item.get("segments") or []
    vehicle_segments = [s for s in segments if (s.get("type") or "") != "walk"]
    return max(0, len(vehicle_segments) - 1)


@tool(args_schema=ScoreRoutesInput)
def score_routes(routes_json: str) -> str:
    """对候选路线按耗时、距离、换乘次数、费用进行加权评分并排序。"""
    data = json.loads(routes_json)
    raw = data.get("routes") if isinstance(data, dict) else data

    candidates: list[RouteCandidate] = []
    for item in raw or []:
        candidates.append(RouteCandidate(
            mode=item.get("mode", ""),
            distance_km=float(item.get("distance_km") or 0),
            duration_min=float(item.get("duration_min") or 0),
            transfers=int(item.get("transfers") or _count_transfers(item)),
            cost=_parse_cost(item),
        ))

    if not candidates:
        return json.dumps({"error": "没有可评分的路线候选"}, ensure_ascii=False)

    profile = load_profile()
    weights = compute_route_weights(profile)
    scored = RouteScorer().score(candidates, weights=weights)

    return json.dumps(
        {
            "weights": weights,
            "profile_tags": profile.tags,
            "results": [item.model_dump() for item in scored],
        },
        ensure_ascii=False,
        indent=2,
    )
