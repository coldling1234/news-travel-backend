"""高德地图 Web API 客户端 — POI 搜索、地理编码、路线规划、酒店价格查询。"""
"""Synchronous HTTP client for Amap (高德地图) Web API."""

import json
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from config.settings import settings


BASE_URL = "https://restapi.amap.com/v3"

CATEGORY_CODES: dict[str, str] = {
    "attraction": (
        "110000|120000|130000|140000|150000|160000|170000|180000|190000|200000"
    ),
    "restaurant": "050000",
    "hotel": "060000|070000|080000",
}

DRIVING_STRATEGIES: dict[str, str] = {
    "fastest": "0",
    "shortest": "2",
    "avoid_highway": "3",
    "walk_first": "4",
}


class AmapClient:
    """高德地图 Web API 客户端。

    封装 POI 搜索、地理编码、驾车/公交/步行路线规划。
    search_hotels() 方法用于 estimate_budget 工具查询酒店价格。
    """
    """Low-level HTTP client wrapping Amap Web API endpoints."""

    _DEFAULT_TIMEOUT = 15

    # ------------------------------------------------------------------
    # POI search
    # ------------------------------------------------------------------

    def text_search(
        self,
        keywords: str,
        types: Optional[str] = None,
        city: Optional[str] = None,
        citylimit: bool = False,
        offset: int = 10,
        page: int = 1,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "keywords": keywords,
            "offset": min(offset, 25),
            "page": page,
            "extensions": "all",
        }
        if types:
            params["types"] = types
        if city:
            params["city"] = city
            params["citylimit"] = str(citylimit).lower()
        return self._get("/place/text", params)

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    def geocode(
        self, address: str, city: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "address": address,
        }
        if city:
            params["city"] = city
        return self._get("/geocode/geo", params)

    # ------------------------------------------------------------------
    # Direction / routing
    # ------------------------------------------------------------------

    def direction_driving(
        self, origin: str, destination: str, strategy: str = "fastest",
    ) -> dict[str, Any]:
        s = DRIVING_STRATEGIES.get(strategy, "0")
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
            "strategy": s,
            "extensions": "all",
            "show_fields": "cost,tmcs",
        }
        return self._get("/direction/driving", params)

    def direction_transit(
        self, origin: str, destination: str,
        city: str, cityd: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": cityd or city,
            "extensions": "all",
        }
        return self._get("/direction/transit/integrated", params)

    def direction_walking(
        self, origin: str, destination: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
        }
        return self._get("/direction/walking", params)

    # ------------------------------------------------------------------
    # Reverse geocode
    # ------------------------------------------------------------------

    def reverse_geocode(self, location: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.AMAP_API_KEY,
            "location": location,
            "extensions": "all",
        }
        return self._get("/geocode/regeo", params)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def geocode_to_coord(
        self, place: str, city: Optional[str] = None,
    ) -> tuple[str, str]:
        result = self.geocode(place, city=city)
        geocodes = result.get("geocodes") or []
        if not geocodes:
            raise ValueError(f"未找到地点 '{place}' 的坐标")
        return geocodes[0]["location"]

    # ------------------------------------------------------------------
    # Hotel price search (used by estimate_budget)
    # ------------------------------------------------------------------

    def search_hotels(
        self,
        city: str,
        keywords: str = "",
        limit: int = 20,
    ) -> Optional[dict[str, Any]]:
        """Search hotels in a city and return per-night price range.

        Uses Amap POI search with hotel category codes, extracts
        ``biz_ext.cost`` from each result to compute min-max.

        Returns dict with range_min_per_night, range_max_per_night,
        hotels_found, source, or None if no priced hotels found.
        """
        data = self.text_search(
            keywords=keywords or city,
            types=CATEGORY_CODES["hotel"],
            city=city,
            offset=limit,
        )
        if not self.amap_status_ok(data):
            return None

        pois = data.get("pois") or []
        costs: list[int] = []
        for poi in pois:
            biz = poi.get("biz_ext") or {}
            cost_str = biz.get("cost")
            if cost_str:
                try:
                    c = int(float(cost_str))
                    if c > 0:
                        costs.append(c)
                except (ValueError, TypeError):
                    pass

        if not costs:
            return None

        return {
            "range_min_per_night": min(costs),
            "range_max_per_night": max(costs),
            "currency": "CNY",
            "hotels_found": len(costs),
            "source": "高德地图 POI 搜索",
        }

    @staticmethod
    def amap_status_ok(data: dict[str, Any]) -> bool:
        return data.get("status") == "1" and data.get("info") == "OK"

    # ------------------------------------------------------------------
    # Internal HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = requests.get(
                    url, params=params, timeout=self._DEFAULT_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(
            f"Amap API request failed after 3 retries: {last_exc}"
        )
