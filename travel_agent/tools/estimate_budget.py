"""Tool: estimate_budget — estimate travel costs with range estimates.

Uses Amap POI search for hotel prices,
heuristic data for transport, dining, and attractions.
All values are ranges — never precise prices.
"""

import json
from datetime import datetime
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from config.settings import settings
from ..amap_client import AmapClient
from ..models.preference import TravelPreference


class EstimateBudgetInput(BaseModel):
    """Input schema for estimate_budget."""
    preference_json: str = Field(
        ..., description="TravelPreference 的 JSON 字符串",
    )


# ---------------------------------------------------------------------------
# Heuristic data
# ---------------------------------------------------------------------------

CHINA_MAJOR_PRICES: dict[tuple[str, str], tuple[int, int, str]] = {
    ("上海", "杭州"): (50, 120, "高铁"),
    ("上海", "南京"): (100, 200, "高铁"),
    ("上海", "北京"): (400, 1500, "高铁/飞机"),
    ("上海", "广州"): (500, 2000, "飞机"),
    ("上海", "成都"): (600, 2500, "飞机"),
    ("北京", "天津"): (30, 80, "高铁"),
    ("北京", "西安"): (400, 1200, "高铁"),
    ("北京", "广州"): (600, 2500, "飞机"),
    ("广州", "深圳"): (30, 100, "高铁/城际"),
    ("广州", "珠海"): (50, 100, "城际"),
    ("成都", "重庆"): (100, 200, "高铁"),
    ("深圳", "香港"): (20, 80, "高铁/地铁"),
}

HEURISTIC_TRANSPORT: dict[str, tuple[int, int]] = {
    "高铁_短途": (50, 200),
    "高铁_中途": (200, 600),
    "高铁_长途": (500, 1000),
    "飞机_国内": (400, 2500),
    "飞机_国际_短途": (1000, 4000),
    "飞机_国际_长途": (3000, 10000),
}

HEURISTIC_HOTEL: dict[str, tuple[int, int]] = {
    "酒店": (200, 800),
    "民宿": (150, 500),
    "青旅": (50, 150),
    "豪华度假村": (800, 3000),
    "经济型酒店": (100, 300),
    "default": (150, 600),
}

DINING_RANGE = (50, 150)
ATTRACTION_RANGE = (30, 200)
LOCAL_TRANSPORT_RANGE = (10, 50)


def _transport_mode(dep: str, dest: str) -> str:
    for (a, b), (_, _, m) in CHINA_MAJOR_PRICES.items():
        if dep in (a, b) and dest in (a, b):
            return m
    return "高铁/飞机"


def _heuristic_transport(dep: str, dest: str, mode: str) -> tuple[int, int, str]:
    for (a, b), (lo, hi, _) in CHINA_MAJOR_PRICES.items():
        if dep in (a, b) and dest in (a, b):
            return lo, hi, "中国主要城市间启发式估算"
    if "飞机" in mode:
        return (*HEURISTIC_TRANSPORT["飞机_国内"], "启发式估算")
    if "高铁" in mode:
        return (*HEURISTIC_TRANSPORT["高铁_中途"], "启发式估算")
    return (*HEURISTIC_TRANSPORT["高铁_短途"], "启发式估算")


def _heuristic_hotel(accommodation: Optional[str]) -> tuple[int, int, str]:
    if accommodation:
        for key, (lo, hi) in HEURISTIC_HOTEL.items():
            if key in accommodation:
                return lo, hi, f"启发式估算（{key}）"
    return (*HEURISTIC_HOTEL["default"], "启发式估算")


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool(args_schema=EstimateBudgetInput)
def estimate_budget(preference_json: str) -> str:
    """估算旅行各项花费（区间估算，不做精确报价）。

    使用高德地图 POI 搜索获取酒店价格区间，
    使用中国主要城市间启发式数据估算交通费用，
    餐饮、景点、市内交通基于人均消费启发式估算。

    Args:
        preference_json: TravelPreference 的 JSON 字符串。
    """
    try:
        data = json.loads(preference_json)
        pref = TravelPreference(**data)
    except Exception as e:
        return json.dumps({"error": f"无法解析偏好 JSON: {e}"}, ensure_ascii=False)

    missing = pref.get_missing_fields()
    if missing:
        return json.dumps(
            {"error": "缺少必填字段，无法估算预算", "missing_fields": missing},
            ensure_ascii=False,
        )

    dep = pref.departure or ""
    dest = pref.destination or ""
    travelers = pref.travelers or 1
    start = pref.start_date or ""
    end = pref.end_date or ""

    try:
        d0 = datetime.strptime(start, "%Y-%m-%d")
        d1 = datetime.strptime(end, "%Y-%m-%d")
        trip_days = max((d1 - d0).days + 1, 1)
        trip_nights = max(trip_days - 1, 1)
    except ValueError:
        trip_days = 2
        trip_nights = 1

    # ------------------------------------------------------------------
    # 1. Transport (heuristic)
    # ------------------------------------------------------------------
    mode = _transport_mode(dep, dest)
    lo, hi, src = _heuristic_transport(dep, dest, mode)

    transport_items: list[dict[str, Any]] = [{
        "category": "交通",
        "item": f"往返交通（{mode}）",
        "range_min": lo * travelers,
        "range_max": hi * travelers,
        "per_person": False,
        "source": src,
    }]

    # Local transport
    lt_lo, lt_hi = LOCAL_TRANSPORT_RANGE
    transport_items.append({
        "category": "交通",
        "item": "市内交通",
        "range_min": lt_lo * trip_days * travelers,
        "range_max": lt_hi * trip_days * travelers,
        "per_day": True,
        "source": "启发式估算",
    })

    # ------------------------------------------------------------------
    # 2. Accommodation (Amap + heuristic fallback)
    # ------------------------------------------------------------------
    hotel_lo, hotel_hi, hotel_source = _heuristic_hotel(pref.accommodation_type)
    amap_ok = bool(settings.AMAP_API_KEY)

    if amap_ok:
        try:
            amap = AmapClient()
            hr = amap.search_hotels(dest, limit=20)
            if hr:
                hotel_lo = hr["range_min_per_night"]
                hotel_hi = hr["range_max_per_night"]
                hotel_source = hr["source"]
        except Exception:
            pass

    accommodation_items = [{
        "category": "住宿",
        "item": f"住宿（{trip_nights}晚）",
        "range_min": hotel_lo * trip_nights,
        "range_max": hotel_hi * trip_nights,
        "per_night_range": [hotel_lo, hotel_hi],
        "source": hotel_source,
    }]

    # ------------------------------------------------------------------
    # 3. Dining
    # ------------------------------------------------------------------
    dn_lo, dn_hi = DINING_RANGE
    meals = 3
    dining_items = [{
        "category": "餐饮",
        "item": f"每日{meals}餐 x {trip_days}天 x {travelers}人",
        "range_min": dn_lo * meals * trip_days * travelers,
        "range_max": dn_hi * meals * trip_days * travelers,
        "per_meal_range": [dn_lo, dn_hi],
        "source": "启发式估算",
    }]

    # ------------------------------------------------------------------
    # 4. Attractions
    # ------------------------------------------------------------------
    at_lo, at_hi = ATTRACTION_RANGE
    per_day = 2
    attraction_items = [{
        "category": "景点门票",
        "item": f"每日{per_day}个景点 x {trip_days}天 x {travelers}人",
        "range_min": at_lo * per_day * trip_days * travelers,
        "range_max": at_hi * per_day * trip_days * travelers,
        "per_attraction_range": [at_lo, at_hi],
        "source": "启发式估算",
    }]

    # ------------------------------------------------------------------
    # Totals
    # ------------------------------------------------------------------
    all_items = transport_items + accommodation_items + dining_items + attraction_items
    total_min = sum(i["range_min"] for i in all_items)
    total_max = sum(i["range_max"] for i in all_items)

    return json.dumps(
        {
            "trip_summary": f"{dep} -> {dest}, {trip_days}天{trip_nights}晚, {travelers}人",
            "data_sources": {
                "transport": "中国主要城市间启发式估算",
                "hotels": "高德地图 POI 搜索" if amap_ok else "启发式估算",
                "other": "启发式估算",
            },
            "disclaimer": "所有价格为区间估算，并非精确报价。实际价格可能因季节、预订时间、房型等因素有所不同。",
            "items": all_items,
            "total_range": {"min": total_min, "max": total_max},
            "confidence": "medium",
        },
        ensure_ascii=False,
        indent=2,
    )
