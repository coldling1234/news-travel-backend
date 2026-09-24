"""Tool: collect_preferences — structure user travel preferences from NL input."""

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..models.preference import TravelPreference
from ..pipeline import PreferencePipeline
from ..profile import update_profile_from_preference


class CollectPreferencesInput(BaseModel):
    """Input schema for collect_preferences."""
    user_input: str = Field(..., description="用户的自然语言旅行需求描述")


@tool(args_schema=CollectPreferencesInput)
def collect_preferences(user_input: str) -> str:
    """从用户的自然语言描述中一次性提取结构化的旅行偏好。

    不做交互式追问。只提取 4 个必要字段和可选字段，缺失字段通过
    missing_fields 返回，由 Agent 在对话中继续追问。
    同时维护用户画像，供后续评分工具动态调整维度权重。
    返回 JSON：{preference: TravelPreference, raw_input, summary, missing_fields}。
    """
    # One-shot extraction (no interactive follow-up for tool context)
    pipeline = PreferencePipeline()
    preference, summary = pipeline.run_one_shot(user_input)

    update_profile_from_preference(preference)

    return json.dumps(
        {
            "preference": preference.model_dump(exclude_none=True),
            "raw_input": user_input,
            "summary": summary,
            "missing_fields": preference.get_missing_fields(),
        },
        ensure_ascii=False,
        indent=2,
    )
