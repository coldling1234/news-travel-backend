"""用户画像与评分权重 — 维护用户偏好并动态调整各维度权重。"""

import json
import os

from pydantic import BaseModel, Field

from .models.preference import TravelPreference


PROFILE_DIR = "data"
PROFILE_FILE = os.path.join(PROFILE_DIR, "user_profile.json")

HOTEL_DIMENSIONS = ["rating", "location", "quietness"]
ROUTE_DIMENSIONS = ["duration", "distance", "transfers", "cost"]

BASE_HOTEL_WEIGHTS = {"rating": 0.35, "location": 0.35, "quietness": 0.30}
BASE_ROUTE_WEIGHTS = {"duration": 0.30, "distance": 0.20, "transfers": 0.25, "cost": 0.25}

# 用户标签 -> 维度权重放大系数
HOTEL_WEIGHT_ADJUSTMENTS = {
    "安静": {"quietness": 1.8},
}

ROUTE_WEIGHT_ADJUSTMENTS = {
    "省钱": {"cost": 1.8},
    "少换乘": {"transfers": 1.8},
    "省时": {"duration": 1.8},
    "少走路": {"distance": 1.5},
}

# 用户偏好描述关键字 -> 归一化标签
_TAG_KEYWORDS = {
    "安静": ("安静", "清静", "静谧", "幽静", "喧闹", "吵闹", "嘈杂", "人多"),
    "省钱": ("省钱", "预算", "性价比", "便宜"),
    "少换乘": ("少换乘", "直达", "不换乘"),
    "省时": ("省时", "快", "节省时间"),
    "少走路": ("少走路", "步行少", "距离近"),
}


class UserProfile(BaseModel):
    """用户画像，保存归一化后的偏好标签。"""

    tags: list[str] = Field(default_factory=list)


def load_profile() -> UserProfile:
    """从磁盘加载用户画像，文件不存在或损坏时返回空画像。"""
    if not os.path.exists(PROFILE_FILE):
        return UserProfile()
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return UserProfile(**json.load(f))
    except (json.JSONDecodeError, OSError, TypeError):
        return UserProfile()


def save_profile(profile: UserProfile) -> None:
    """将用户画像写入磁盘。"""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)


def extract_tags_from_preference(pref: TravelPreference) -> list[str]:
    """从一次旅行偏好中提取归一化标签。"""
    texts: list[str] = []
    for value in (pref.interests or []):
        texts.append(str(value))
    for value in (pref.avoid or []):
        texts.append(str(value))
    if pref.accommodation_type:
        texts.append(str(pref.accommodation_type))

    tags: list[str] = []
    for tag, keywords in _TAG_KEYWORDS.items():
        if any(any(keyword in text for keyword in keywords) for text in texts):
            tags.append(tag)
    return tags


def update_profile_from_preference(pref: TravelPreference) -> UserProfile:
    """根据本次偏好合并更新画像，新标签追加、已有标签保留。"""
    profile = load_profile()
    new_tags = extract_tags_from_preference(pref)
    profile = UserProfile(tags=list(dict.fromkeys(profile.tags + new_tags)))
    save_profile(profile)
    return profile


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        count = len(weights)
        return {key: 1.0 / count for key in weights}
    return {key: value / total for key, value in weights.items()}


def compute_hotel_weights(profile: UserProfile) -> dict[str, float]:
    """根据画像计算酒店各维度权重（归一化到总和为 1）。"""
    weights = dict(BASE_HOTEL_WEIGHTS)
    for tag in profile.tags:
        adjustments = HOTEL_WEIGHT_ADJUSTMENTS.get(tag)
        if adjustments:
            for dimension, multiplier in adjustments.items():
                if dimension in weights:
                    weights[dimension] *= multiplier
    return _normalize_weights(weights)


def compute_route_weights(profile: UserProfile) -> dict[str, float]:
    """根据画像计算路线各维度权重（归一化到总和为 1）。"""
    weights = dict(BASE_ROUTE_WEIGHTS)
    for tag in profile.tags:
        adjustments = ROUTE_WEIGHT_ADJUSTMENTS.get(tag)
        if adjustments:
            for dimension, multiplier in adjustments.items():
                if dimension in weights:
                    weights[dimension] *= multiplier
    return _normalize_weights(weights)
