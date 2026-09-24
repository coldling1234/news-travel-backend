"""Open-Meteo 免费天气 API 客户端 — 地理编码、逐日天气预报、WMO 天气码中文化。

Open-Meteo 完全免费，无需注册或 API Key，提供全球 16 天天气预报。
API 文档: https://open-meteo.com/en/docs
地理编码: https://open-meteo.com/en/docs/geocoding-api
"""

import json          # JSON 解析（API 返回 JSON）
import time          # 重试间隔
from typing import Any, Optional  # 类型标注

import requests     # HTTP 客户端


# ═══════════════════════════════════════════════════════════════════════════════
# WMO 天气码 → 中文描述 映射表
# 参考: https://open-meteo.com/en/docs (WMO Weather interpretation codes)
# ═══════════════════════════════════════════════════════════════════════════════

WMO_CODES: dict[int, str] = {
    # ── 晴/多云 ──
    0: "晴天",
    1: "晴间多云",
    2: "多云",
    3: "阴天",
    # ── 雾 ──
    45: "雾",
    48: "雾凇",
    # ── 小雨/毛毛雨 ──
    51: "小雨",
    53: "小雨",
    55: "小雨",
    # ── 冻雨 ──
    56: "冻雨",
    57: "冻雨",
    # ── 中-大雨 ──
    61: "中雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    # ── 小雪-大雪 ──
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    # ── 阵雨 ──
    80: "阵雨",
    81: "中阵雨",
    82: "大阵雨",
    # ── 阵雪 ──
    85: "阵雪",
    86: "大阵雪",
    # ── 雷暴 ──
    95: "雷暴",
    96: "雷暴伴冰雹",
    99: "雷暴伴冰雹",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 出行建议生成器
# ═══════════════════════════════════════════════════════════════════════════════

def generate_travel_advice(days: list[dict[str, Any]]) -> list[str]:
    """根据每天的天气数据，逐日生成中文出行建议。

    根据天气码（晴/雨/雷暴）、降水概率、气温、紫外线、风速
    自动匹配对应的出行提示。

    Args:
        days: 逐日天气字典列表，每项包含 weather_code、temperature_2m_max、
              precipitation_probability_max、uv_index_max、wind_speed_10m_max 等。

    Returns:
        与 days 等长的字符串列表，每项形如 "2026-08-01: 建议携带雨具; 准备室内备选景点"
    """
    advice: list[str] = []                               # 结果列表
    for d in days:                                       # 遍历每一天
        tips: list[str] = []                             # 当天的提示列表

        code = d.get("weather_code", 0)                  # WMO 天气码（默认 0 = 晴天）
        precip = d.get("precipitation_probability_max", 0) or 0  # 降水概率百分比
        temp_max = d.get("temperature_2m_max", 25)       # 当日最高温（℃）
        uv = d.get("uv_index_max", 3)                    # 紫外线指数
        wind = d.get("wind_speed_10m_max", 0) or 0       # 最大风速（km/h）

        # ── 根据天气码给出基础建议 ──────────────────────────
        if code in (0, 1):                               # 晴天/晴间多云
            tips.append("适合户外活动")
        elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):  # 各类降雨
            tips.append("建议携带雨具")
            tips.append("准备室内备选景点")
        elif code in (95, 96, 99):                       # 雷暴
            tips.append("有雷暴风险，避免户外高地活动")
        elif code in (45, 48):                           # 雾
            tips.append("能见度较低，注意交通安全")

        # ── 降水概率 ──────────────────────────────────────
        if precip and precip > 60:                       # 高降水概率
            tips.append(f"降水概率 {precip}%，强烈建议备好雨具")
        elif precip and precip > 30:                     # 中等降水概率
            tips.append(f"降水概率 {precip}%，建议关注天气变化")

        # ── 极端温度 ──────────────────────────────────────
        if temp_max > 35:                                # 高温
            tips.append("高温天气，注意防暑防晒")
        elif temp_max < 5:                               # 低温
            tips.append("低温天气，注意保暖")

        # ── 紫外线 ────────────────────────────────────────
        if uv and uv >= 6:                               # 高紫外线
            tips.append(f"紫外线指数 {uv}，做好防晒")

        # ── 大风 ──────────────────────────────────────────
        if wind and wind > 20:                           # 风速 > 20 km/h
            tips.append(f"风速 {wind} km/h，注意防风")

        # ── 兜底 ─────────────────────────────────────────
        if not tips:                                     # 没有任何风险提示
            tips.append("天气状况良好，出行无忧")

        # 格式化为单行: "YYYY-MM-DD: tip1; tip2; ..."
        advice.append(f"{d['date']}: {'; '.join(tips)}")

    return advice


# ═══════════════════════════════════════════════════════════════════════════════
# Open-Meteo 客户端
# ═══════════════════════════════════════════════════════════════════════════════

class WeatherClient:
    """Open-Meteo 免费天气 API 客户端。

    三个核心方法:
        geocode()         — 地名 → 坐标（调用 Geocoding API）
        forecast_daily()  — 获取逐日天气预报（调用 Forecast API）
        get_weather()     — 一站式: geocode + forecast + 格式化输出

    无需 API Key，免费使用，每个 IP 每天有请求频率限制。
    """

    # API 端点
    _GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"  # 地理编码
    _FORECAST_URL = "https://api.open-meteo.com/v1/forecast"           # 天气预报

    # 常量
    _TIMEOUT = 15      # HTTP 请求超时（秒）
    _MAX_RETRIES = 3   # 最大重试次数
    _RETRY_DELAY = 0.5 # 重试间隔基础值（秒）

    # ═══════════════════════════════════════════════════════════════════════
    # 地理编码
    # ═══════════════════════════════════════════════════════════════════════

    def geocode(self, name: str, count: int = 5) -> list[dict[str, Any]]:
        """根据地名查询候选坐标列表。

        调用 Open-Meteo Geocoding API，返回按相关度排序的候选结果。

        Args:
            name: 地点名称，如 "杭州"、"Tokyo"、"Paris"。
            count: 最大返回候选数。

        Returns:
            候选列表，每项包含 name / country / admin1 / latitude / longitude。
        """
        # 构建请求参数
        params = {
            "name": name,           # 查询地名
            "count": count,         # 最多返回 N 个候选
            "language": "zh",       # 返回中文地名
            "format": "json",       # JSON 格式
        }

        data = self._get(self._GEOCODING_URL, params)     # 发送 GET 请求
        results = data.get("results") or []               # 提取 results 数组

        out: list[dict[str, Any]] = []                    # 构建标准化的输出
        for r in results:
            out.append({
                "name": r.get("name", ""),                # 地点名
                "country": r.get("country", ""),          # 国家
                "admin1": r.get("admin1", ""),            # 省/州（用于消歧）
                "latitude": r.get("latitude"),            # 纬度
                "longitude": r.get("longitude"),          # 经度
            })
        return out

    # ═══════════════════════════════════════════════════════════════════════
    # 逐日天气预报
    # ═══════════════════════════════════════════════════════════════════════

    def forecast_daily(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        """根据经纬度获取逐日天气预报（原始 JSON）。

        Args:
            latitude: 纬度。
            longitude: 经度。
            forecast_days: 预报天数（1-16，Open-Meteo 上限 16 天）。

        Returns:
            Open-Meteo Forecast API 的原始解析 JSON，daily 字段包含逐日数组。
        """
        # 构建请求参数
        params: dict[str, Any] = {
            "latitude": latitude,                         # 纬度
            "longitude": longitude,                       # 经度

            # daily 参数: 逗号分隔的变量列表（Open-Meteo 特有格式）
            "daily": (
                "weather_code,"                            # WMO 天气码
                "temperature_2m_max,"                      # 最高温
                "temperature_2m_min,"                      # 最低温
                "precipitation_sum,"                       # 总降水量
                "precipitation_probability_max,"           # 最大降水概率
                "wind_speed_10m_max,"                      # 最大风速
                "uv_index_max,"                            # 紫外线指数
                "sunrise,"                                 # 日出时间
                "sunset"                                   # 日落时间
            ),

            "timezone": "auto",                            # 自动检测时区
            "forecast_days": min(forecast_days, 14),       # 上限 14 天（含今天）
        }

        return self._get(self._FORECAST_URL, params)      # 发送 GET 请求

    # ═══════════════════════════════════════════════════════════════════════
    # 一站式天气查询（对外主接口）
    # ═══════════════════════════════════════════════════════════════════════

    def get_weather(
        self,
        location: str,
        forecast_days: int = 7,
    ) -> list[dict[str, Any]]:
        """一站式天气查询：geocode + forecast + 结构化输出。

        这是 get_weather 工具调用的核心方法：
        1. 通过地名查询坐标（geocode）
        2. 根据坐标获取逐日预报（forecast_daily）
        3. 将原始数据解析为结构化 dict 列表

        Args:
            location: 城市或地点名称，如 "杭州"、"Tokyo"。
            forecast_days: 需要的预报天数（1-14）。

        Returns:
            结构化天气列表。每项包含 date / condition / temperature_2m_max /
            temperature_2m_min / precipitation_sum / precipitation_probability_max /
            wind_speed_10m_max / uv_index_max / sunrise / sunset / resolved_location。

        Raises:
            ValueError: 无法 geocode 到指定地点。
        """
        # ── Step 1: 地理编码（地名 → 坐标）─────────────────
        candidates = self.geocode(location)                # 查询候选列表
        if not candidates:                                 # 没找到该地点
            raise ValueError(
                f"无法找到地点 '{location}'，请检查名称拼写"
            )

        # ── Step 2: 选取最佳候选 ──────────────────────────
        best = candidates[0]                               # 取第一个（最相关）候选
        lat = float(best["latitude"])                      # 提取纬度
        lon = float(best["longitude"])                     # 提取经度

        # 组装"已解析地名"（含省/州和国家信息）
        resolved_name = best["name"]                       # 基础地名
        if best.get("admin1"):                             # 有省/州信息
            resolved_name += f", {best['admin1']}"
        if best.get("country"):                            # 有国家信息
            resolved_name += f", {best['country']}"

        # ── Step 3: 获取逐日预报 ─────────────────────────
        data = self.forecast_daily(lat, lon, forecast_days)  # 调用 Open-Meteo API
        daily = data.get("daily") or {}                    # 提取 daily 对象

        # ── Step 4: 提取各字段数组 ────────────────────────
        # Open-Meteo 返回的 daily 字段是并行数组结构
        # 例如 dates[0] 对应 codes[0], temps_max[0], ...
        dates = daily.get("time") or []                    # 日期数组 ["2026-08-01", ...]
        codes = daily.get("weather_code") or []            # WMO 天气码数组
        temps_max = daily.get("temperature_2m_max") or []  # 最高温数组
        temps_min = daily.get("temperature_2m_min") or []  # 最低温数组
        precip_sum = daily.get("precipitation_sum") or []  # 降水量数组
        precip_prob = daily.get("precipitation_probability_max") or []  # 降水概率数组
        wind_max = daily.get("wind_speed_10m_max") or []   # 风速数组
        uv_max = daily.get("uv_index_max") or []           # 紫外线数组
        sunrises = daily.get("sunrise") or []              # 日出时间数组
        sunsets = daily.get("sunset") or []                # 日落时间数组

        # ── Step 5: 逐天组装结构化输出 ─────────────────────
        results: list[dict[str, Any]] = []
        for i in range(len(dates)):                         # 遍历每一天
            code_val = int(codes[i]) if i < len(codes) else 0  # 安全取天气码

            results.append({
                # 日期与天气
                "date": dates[i],                                         # 日期 YYYY-MM-DD
                "condition": WMO_CODES.get(code_val, f"未知({code_val})"),  # WMO→中文
                "weather_code": code_val,                                 # 原始 WMO 码

                # 温度
                "temperature_2m_max": temps_max[i] if i < len(temps_max) else None,
                "temperature_2m_min": temps_min[i] if i < len(temps_min) else None,

                # 降水
                "precipitation_sum": precip_sum[i] if i < len(precip_sum) else None,
                "precipitation_probability_max": precip_prob[i] if i < len(precip_prob) else None,

                # 风 / 紫外线
                "wind_speed_10m_max": wind_max[i] if i < len(wind_max) else None,
                "uv_index_max": uv_max[i] if i < len(uv_max) else None,

                # 日出日落
                "sunrise": sunrises[i] if i < len(sunrises) else None,
                "sunset": sunsets[i] if i < len(sunsets) else None,

                # 元信息
                "resolved_location": resolved_name,                        # 已解析的完整地名
            })

        return results

    # ═══════════════════════════════════════════════════════════════════════
    # 内部 HTTP 请求（含重试）
    # ═══════════════════════════════════════════════════════════════════════

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """底层 HTTP GET 请求，含 3 次重试和指数退避。

        Args:
            url: 完整的 API 端点 URL。
            params: URL 查询参数字典。

        Returns:
            解析后的 JSON dict。

        Raises:
            RuntimeError: 3 次重试后仍然失败。
        """
        last_exc: Optional[Exception] = None                # 记录最后一次异常

        for attempt in range(self._MAX_RETRIES):            # 最多重试 3 次
            try:
                resp = requests.get(                        # 发送 GET 请求
                    url,
                    params=params,                          # URL 查询参数
                    timeout=self._TIMEOUT,                  # 超时时间
                )
                resp.raise_for_status()                     # 非 2xx → 抛出异常
                return resp.json()                          # 解析 JSON 并返回

            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_exc = exc                              # 记录异常
                if attempt < self._MAX_RETRIES - 1:         # 不是最后一次
                    time.sleep(self._RETRY_DELAY * (attempt + 1))  # 指数退避

        # 重试耗尽 → 抛出
        raise RuntimeError(
            f"Open-Meteo API request failed after "
            f"{self._MAX_RETRIES} retries: {last_exc}"
        )
