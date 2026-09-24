"""约束摘要 — 将 TravelPreference 格式化为终端友好的中文摘要。"""
"""Render a TravelPreference into a readable Chinese constraint summary."""

from .models.preference import TravelPreference


class ConstraintSummarizer:
    """约束摘要生成器。将 TravelPreference 格式化为终端友好的中文摘要。"""
    """Format a complete (or partial) TravelPreference as a readable summary."""

    def summarize(self, preference: TravelPreference) -> str:
        """生成格式化的中文约束摘要，适合终端打印。"""
        lines: list[str] = []
        lines.append("=" * 48)
        lines.append("  📋  旅行约束摘要")
        lines.append("=" * 48)

        self._add_section(lines, "📍 行程概览")
        self._add_field(lines, "目的地", preference.destination)
        self._add_field(lines, "出发地", preference.departure)
        self._add_field(lines, "出发日期", preference.start_date)
        self._add_field(lines, "返程日期", preference.end_date)

        has_optional_1 = any([
            preference.budget_range,
            preference.travelers,
        ])
        if has_optional_1:
            self._add_section(lines, "💰 预算与人数")
            self._add_field(lines, "预算范围", self._format_budget(preference.budget_range))
            self._add_field(lines, "出行人数", preference.travelers)

        has_optional_2 = any([
            preference.interests,
            preference.must_see,
            preference.avoid,
        ])
        if has_optional_2:
            self._add_section(lines, "🎯 兴趣与偏好")
            self._add_list_field(lines, "兴趣标签", preference.interests)
            self._add_list_field(lines, "必去景点", preference.must_see)
            self._add_list_field(lines, "避开项", preference.avoid)

        has_optional_3 = any([
            preference.accommodation_type,
            preference.transport_preference,
        ])
        if has_optional_3:
            self._add_section(lines, "🏨 住宿与交通")
            self._add_field(lines, "住宿偏好", preference.accommodation_type)
            self._add_field(lines, "交通偏好", preference.transport_preference)

        # Missing required fields warning
        missing = preference.get_missing_fields()
        if missing:
            self._add_section(lines, "⚠️  缺失必填项")
            for field_name in missing:
                self._add_field(lines, self._field_label(field_name), "（未填写）")

        lines.append("=" * 48)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_section(lines: list[str], title: str) -> None:
        lines.append("")
        lines.append(f"  {title}")

    @staticmethod
    def _add_field(
        lines: list[str], label: str, value: str | int | None
    ) -> None:
        if value is not None and value != "":
            lines.append(f"    {label}: {value}")

    @staticmethod
    def _add_list_field(
        lines: list[str], label: str, values: list[str] | None
    ) -> None:
        if values:
            joined = "、".join(values)
            lines.append(f"    {label}: {joined}")

    @staticmethod
    def _format_budget(budget: list[int] | None) -> str | None:
        if budget and len(budget) == 2:
            return f"{budget[0]:,} - {budget[1]:,} 元"
        return None

    @staticmethod
    def _field_label(field_name: str) -> str:
        _LABELS: dict[str, str] = {
            "destination": "目的地",
            "departure": "出发地",
            "start_date": "出发日期",
            "end_date": "返程日期",
        }
        return _LABELS.get(field_name, field_name)
