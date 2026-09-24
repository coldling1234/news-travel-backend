"""Travel preference data model with field descriptions used as LLM hints."""

from typing import ClassVar, Optional
from pydantic import BaseModel, Field, field_validator


class TravelPreference(BaseModel):
    """结构化的旅行偏好数据模型。

    必填字段（4个）: destination, departure, start_date, end_date
    可选字段（7个）: budget_range, travelers, interests,
                   must_see, avoid, accommodation_type,
                   transport_preference
    """
    """Structured travel preference extracted from natural language input.

    Required fields: destination, departure, start_date, end_date.
    Optional fields carry additional constraints for downstream planning.
    """

    destination: Optional[str] = Field(
        default=None,
        description="旅行目的地城市或地区名称，例如：北京、东京、巴黎",
    )
    departure: Optional[str] = Field(
        default=None,
        description="出发城市或地区名称，例如：上海、深圳、纽约",
    )
    start_date: Optional[str] = Field(
        default=None,
        description="行程开始日期，格式为 YYYY-MM-DD，例如：2026-08-01",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="行程结束日期，格式为 YYYY-MM-DD，例如：2026-08-07",
    )
    budget_range: Optional[list[int]] = Field(
        default=None,
        description="预算范围（人民币），包含最小值和最大值，例如：[3000, 8000] 表示 3000-8000 元",
    )
    travelers: Optional[int] = Field(
        default=None,
        description="旅行人数，包括用户本人",
    )
    interests: Optional[list[str]] = Field(
        default=None,
        description="兴趣偏好标签列表，例如：[\"美食\", \"历史\", \"自然风光\", \"购物\"]",
    )
    must_see: Optional[list[str]] = Field(
        default=None,
        description="必须去的景点或地点列表，例如：[\"故宫\", \"长城\"]",
    )
    avoid: Optional[list[str]] = Field(
        default=None,
        description="需要避开的地点、活动或事物列表，例如：[\"人多的景点\", \"爬山\"]",
    )
    accommodation_type: Optional[str] = Field(
        default=None,
        description="住宿偏好类型，例如：酒店、民宿、青旅、豪华度假村",
    )
    transport_preference: Optional[str] = Field(
        default=None,
        description="交通方式偏好，例如：高铁、飞机、自驾、公共交通",
    )

    @field_validator("budget_range")
    @classmethod
    def validate_budget_range(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is not None:
            if len(v) != 2:
                raise ValueError(f"budget_range must have exactly 2 ints, got {len(v)}")
            if v[0] > v[1]:
                raise ValueError(f"budget_range min {v[0]} > max {v[1]}")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            stripped = v.strip()
            parts = stripped.split("-")
            if len(parts) == 3:
                return stripped
            return stripped
        return v

    # ------------------------------------------------------------------
    # Required field tracking
    # ------------------------------------------------------------------

    REQUIRED_FIELDS: ClassVar[list[str]] = [
        "destination", "departure", "start_date", "end_date"
    ]

    @classmethod
    def get_required_fields(cls) -> list[str]:
        """返回必填字段名列表。"""
        return list(cls.REQUIRED_FIELDS)

    def get_missing_fields(self) -> list[str]:
        """返回值为 None 或空字符串的必填字段，用于判断是否需要追问。"""
        missing: list[str] = []
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(self, field_name, None)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing.append(field_name)
        return missing

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(self, other: "TravelPreference") -> "TravelPreference":
        """合并两个偏好：只将 other 中非 None 的字段覆盖 self 中的 None 字段。
        已有值的字段不会被覆盖，确保追问补充的信息不会冲掉已收集的数据。
        """
        """Merge another preference into this one.

        Only fields that are None in *self* are overwritten by
        non-None values from *other*.  Existing values are preserved.
        Returns a new instance; does not mutate either input.
        """
        merged_data = self.model_dump()
        other_data = other.model_dump(exclude_none=True)
        for key, value in other_data.items():
            if merged_data.get(key) is None:
                merged_data[key] = value
        return TravelPreference(**merged_data)
