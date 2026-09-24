"""Tool: plan_trip — generate a detailed travel plan from collected preferences."""

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..planner import TravelPlanGenerator
from ..models.preference import TravelPreference


class PlanTripInput(BaseModel):
    """Input schema for plan_trip — accepts a TravelPreference as JSON."""

    preference_json: str = Field(
        ...,
        description="TravelPreference 的 JSON 序列化字符串，必须包含目的地、出发地、日期等必填字段",
    )


@tool(args_schema=PlanTripInput)
def plan_trip(preference_json: str) -> str:
    """根据已收集的旅行偏好生成详细的旅行计划。

    生成的计划包含：约束摘要、行程总览表、每日详细计划、
    预算拆分表、风险与备选方案。输出为 Markdown 格式。

    Args:
        preference_json: TravelPreference 的 JSON 字符串。
    """
    try:
        data = json.loads(preference_json)
        preference = TravelPreference(**data)
    except Exception as e:
        return json.dumps(
            {"error": f"无法解析偏好 JSON: {e}"},
            ensure_ascii=False,
        )

    generator = TravelPlanGenerator()
    try:
        plan_md = generator.generate(preference)
        return plan_md
    except ValueError as e:
        return json.dumps(
            {"error": str(e), "missing_fields": preference.get_missing_fields()},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"生成计划失败: {e}"},
            ensure_ascii=False,
        )
