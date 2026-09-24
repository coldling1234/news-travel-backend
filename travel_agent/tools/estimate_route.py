"""Tool: estimate_route — estimate distance, duration, and compare transport modes.

Uses Amap direction APIs (driving / transit / walking).
Auto-geocodes origin and destination if coordinates are not provided.
"""

import json
from enum import Enum
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..amap_client import AmapClient


class TransportMode(str, Enum):
    DRIVING = "driving"
    TRANSIT = "transit"
    WALKING = "walking"
    ALL = "all"


class EstimateRouteInput(BaseModel):
    """Input schema for estimate_route."""

    origin: str = Field(
        ...,
        description="出发点名称或坐标（lng,lat），例如：上海市浦东新区、116.397,39.908",
    )
    destination: str = Field(
        ...,
        description="目的地名称或坐标（lng,lat），例如：杭州市西湖区、120.155,30.274",
    )
    mode: TransportMode = Field(
        default=TransportMode.ALL,
        description="交通方式。driving=驾车, transit=公交, walking=步行, all=全部对比",
    )
    city: Optional[str] = Field(
        default=None,
        description="城市名称（用于公交规划时的城市上下文）。自动推断不填也可",
    )


def _is_coord(s: str) -> bool:
    """Check if a string looks like 'lng,lat' coordinates."""
    parts = s.strip().split(",")
    if len(parts) != 2:
        return False
    try:
        float(parts[0])
        float(parts[1])
        return True
    except ValueError:
        return False


def _parse_driving(result: dict) -> Optional[dict]:
    """Extract driving route summary from Amap response."""
    route = result.get("route")
    if not route:
        return None
    paths = route.get("paths") or []
    if not paths:
        return None
    p = paths[0]
    return {
        "mode": "driving",
        "distance_km": round(int(p.get("distance", 0)) / 1000, 1),
        "duration_min": round(int(p.get("duration", 0)) / 60),
        "tolls": p.get("tolls", 0),
        "traffic_lights": p.get("traffic_lights", 0),
        "cost_estimate": f"{p.get('tolls', 0)} 元（仅过路费）" if p.get("tolls") else "免费",
    }


def _parse_transit(result: dict) -> Optional[dict]:
    """Extract public transit route summary from Amap response."""
    route = result.get("route")
    if not route:
        return None
    transits = route.get("transits") or []
    if not transits:
        return None
    t = transits[0]
    return {
        "mode": "transit",
        "distance_km": round(int(t.get("distance", 0)) / 1000, 1),
        "duration_min": round(int(t.get("duration", 0)) / 60),
        "walking_distance_km": round(int(t.get("walking_distance", 0)) / 1000, 1),
        "cost": t.get("cost", 0),
        "segments": [
            {
                "type": s.get("bus", {}).get("type", "walk"),
                "name": s.get("bus", {}).get("buslines", [{}])[0].get("name", "")
                if s.get("bus", {}).get("buslines")
                else "步行",
                "station_start": s.get("bus", {}).get("buslines", [{}])[0].get(
                    "departure_stop", {}
                ).get("name", "")
                if s.get("bus", {}).get("buslines")
                else "",
                "station_end": s.get("bus", {}).get("buslines", [{}])[0].get(
                    "arrival_stop", {}
                ).get("name", "")
                if s.get("bus", {}).get("buslines")
                else "",
            }
            for s in t.get("segments", [])[:5]
        ],
    }


def _parse_walking(result: dict) -> Optional[dict]:
    """Extract walking route summary from Amap response."""
    route = result.get("route")
    if not route:
        return None
    paths = route.get("paths") or []
    if not paths:
        return None
    p = paths[0]
    steps_count = len(p.get("steps") or [])
    return {
        "mode": "walking",
        "distance_km": round(int(p.get("distance", 0)) / 1000, 1),
        "duration_min": round(int(p.get("duration", 0)) / 60),
        "steps": steps_count,
    }


@tool(args_schema=EstimateRouteInput)
def estimate_route(
    origin: str,
    destination: str,
    mode: TransportMode = TransportMode.ALL,
    city: Optional[str] = None,
) -> str:
    """估算两地之间的路程、耗时，对比多种交通方式。

    使用高德地图路线规划 API，支持驾车、公共交通和步行对比。
    如果输入的是地名而不是坐标，会自动先进行地理编码。
    """
    client = AmapClient()

    # Resolve coordinates for origin and destination
    origin_coord = origin if _is_coord(origin) else None
    dest_coord = destination if _is_coord(destination) else None

    resolve_errors: list[str] = []
    if not origin_coord:
        try:
            origin_coord = client.geocode_to_coord(origin)
        except ValueError as e:
            resolve_errors.append(f"origin: {e}")
    if not dest_coord:
        try:
            dest_coord = client.geocode_to_coord(destination)
        except ValueError as e:
            resolve_errors.append(f"destination: {e}")

    if resolve_errors:
        return json.dumps(
            {"error": "无法解析以下地点", "details": resolve_errors},
            ensure_ascii=False,
        )

    assert origin_coord and dest_coord  # for type checker

    modes_to_query: list[TransportMode] = (
        [TransportMode.DRIVING, TransportMode.TRANSIT, TransportMode.WALKING]
        if mode == TransportMode.ALL
        else [mode]
    )

    city_ctx = city or ""
    results: list[dict] = []

    for m in modes_to_query:
        try:
            if m == TransportMode.DRIVING:
                data = client.direction_driving(origin_coord, dest_coord)
                parsed = _parse_driving(data) if client.amap_status_ok(data) else None
            elif m == TransportMode.TRANSIT:
                data = client.direction_transit(origin_coord, dest_coord, city=city_ctx)
                parsed = _parse_transit(data) if client.amap_status_ok(data) else None
            elif m == TransportMode.WALKING:
                data = client.direction_walking(origin_coord, dest_coord)
                parsed = _parse_walking(data) if client.amap_status_ok(data) else None
            else:
                continue

            if parsed:
                results.append(parsed)
        except Exception:
            pass  # skip modes that fail

    if not results:
        return json.dumps(
            {
                "error": "未能获取任何路线信息，请检查起点/终点是否正确",
                "origin": origin,
                "destination": destination,
            },
            ensure_ascii=False,
            indent=2,
        )

    # Build comparison summary
    summary_parts: list[str] = []
    for r in results:
        summary_parts.append(
            f"{r['mode']}: {r['distance_km']} km, {r['duration_min']} 分钟"
        )

    return json.dumps(
        {
            "origin": origin,
            "destination": destination,
            "comparison": summary_parts,
            "routes": results,
        },
        ensure_ascii=False,
        indent=2,
    )
