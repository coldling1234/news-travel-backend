"""推荐评分器 — 对酒店与路线进行多维加权打分，输出可解释结果。"""

import json
import math
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from .config import settings


def _clamp(value: float, lo: float = 1.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, float(value)))


def _parse_coord(text: Optional[str]) -> Optional[tuple[float, float]]:
    if not text:
        return None
    parts = text.strip().split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两个经纬度坐标之间的球面距离（公里）。"""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class HotelCandidate(BaseModel):
    name: str
    rating: Optional[float] = None
    cost: Optional[float] = None
    location: Optional[str] = None
    distance: Optional[float] = None
    address: str = ""
    place_type: str = ""


class RouteCandidate(BaseModel):
    mode: str
    distance_km: float
    duration_min: float
    transfers: int = 0
    cost: Optional[float] = None


class QuietnessScore(BaseModel):
    name: str
    score: int = Field(..., ge=1, le=10)
    reason: str = ""


class QuietnessScores(BaseModel):
    scores: list[QuietnessScore] = Field(default_factory=list)


class ScoredHotel(BaseModel):
    rank: int
    name: str
    total_score: float
    dimension_scores: dict[str, float]
    weights: dict[str, float]
    reasons: dict[str, str] = Field(default_factory=dict)


class ScoredRoute(BaseModel):
    rank: int
    mode: str
    total_score: float
    dimension_scores: dict[str, float]
    weights: dict[str, float]


QUIETNESS_SYSTEM = """你是酒店环境评估专家。请根据酒店名称、类型、地址和区域，估计其安静程度，1-10 分，10 分最安静。
考虑因素：是否靠近主干道、火车站/机场、商圈或景区；是否属于民宿/度假村/经济型酒店等。
{format_instructions}
"""


class HotelScorer:
    """酒店评分器：评分/口碑、位置便利性为客观维度，安静度为 LLM 主观估计。"""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.2,
        )
        self._parser = PydanticOutputParser(pydantic_object=QuietnessScores)

    def score(
        self,
        hotels: list[HotelCandidate],
        weights: dict[str, float],
        reference: Optional[str] = None,
    ) -> list[ScoredHotel]:
        quiet_map = self._estimate_quietness(hotels)
        ref = _parse_coord(reference)

        scored: list[ScoredHotel] = []
        for hotel in hotels:
            dims = {
                "rating": self._rating_score(hotel.rating),
                "location": self._location_score(hotel, ref),
                "quietness": quiet_map[hotel.name].score if hotel.name in quiet_map else 5.0,
            }
            total = sum(weights.get(key, 0.0) * value for key, value in dims.items())
            quiet = quiet_map.get(hotel.name)
            scored.append(ScoredHotel(
                rank=0,
                name=hotel.name,
                total_score=round(total, 2),
                dimension_scores={key: round(value, 2) for key, value in dims.items()},
                weights={key: round(value, 4) for key, value in weights.items()},
                reasons={"quietness": quiet.reason if quiet else "暂无 LLM 估计"},
            ))

        scored.sort(key=lambda item: item.total_score, reverse=True)
        for index, item in enumerate(scored, start=1):
            item.rank = index
        return scored

    @staticmethod
    def _rating_score(rating: Optional[float]) -> float:
        if rating is None:
            return 5.0
        if 0 <= rating <= 5:
            return _clamp(rating * 2.0)
        return _clamp(rating)

    @staticmethod
    def _location_score(hotel: HotelCandidate, ref: Optional[tuple[float, float]]) -> float:
        if ref and hotel.location:
            coord = _parse_coord(hotel.location)
            if coord:
                km = haversine_km(ref[1], ref[0], coord[1], coord[0])
                return _clamp(10.0 - km * 0.5)
        if hotel.distance is not None:
            return _clamp(10.0 - hotel.distance / 1000.0 * 0.5)
        return 5.0

    def _estimate_quietness(self, hotels: list[HotelCandidate]) -> dict[str, QuietnessScore]:
        if not hotels:
            return {}
        items = [
            {"name": hotel.name, "type": hotel.place_type, "address": hotel.address}
            for hotel in hotels
        ]
        format_instructions = self._parser.get_format_instructions()
        system_text = QUIETNESS_SYSTEM.format(format_instructions=format_instructions)
        user_text = json.dumps(items, ensure_ascii=False, indent=2)
        messages = [
            SystemMessage(content=system_text),
            HumanMessage(content=f"请评估以下酒店的安静程度：\n{user_text}"),
        ]
        try:
            response = self._llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            result = self._parser.parse(content)
            return {item.name: item for item in result.scores}
        except Exception:
            return {}


class RouteScorer:
    """路线评分器：耗时、距离、换乘次数、费用，数值越小得分越高。"""

    def score(
        self,
        routes: list[RouteCandidate],
        weights: dict[str, float],
    ) -> list[ScoredRoute]:
        duration = self._minmax([route.duration_min for route in routes])
        distance = self._minmax([route.distance_km for route in routes])
        transfers = self._minmax([float(route.transfers) for route in routes])
        cost = self._minmax([route.cost for route in routes])

        scored: list[ScoredRoute] = []
        for index, route in enumerate(routes):
            dims = {
                "duration": duration[index],
                "distance": distance[index],
                "transfers": transfers[index],
                "cost": cost[index],
            }
            total = sum(weights.get(key, 0.0) * value for key, value in dims.items())
            scored.append(ScoredRoute(
                rank=0,
                mode=route.mode,
                total_score=round(total, 2),
                dimension_scores={key: round(value, 2) for key, value in dims.items()},
                weights={key: round(value, 4) for key, value in weights.items()},
            ))

        scored.sort(key=lambda item: item.total_score, reverse=True)
        for index, item in enumerate(scored, start=1):
            item.rank = index
        return scored

    @staticmethod
    def _minmax(values: list[Optional[float]]) -> list[float]:
        present = [value for value in values if value is not None]
        if not present:
            return [5.0] * len(values)
        lo, hi = min(present), max(present)
        result: list[float] = []
        for value in values:
            if value is None:
                result.append(5.0)
            elif hi == lo:
                result.append(5.0)
            else:
                result.append(_clamp(10.0 - (value - lo) / (hi - lo) * 9.0))
        return result
