"""旅行计划生成器 — 偏好 + 天气 + 历史 → LLM → 结构化 Markdown 计划。"""

import json
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings
from .models.preference import TravelPreference


PLANNER_SYSTEM = """你是一位资深的旅行规划师，拥有丰富的中国及国际旅游规划经验。
你需要根据用户的旅行偏好，生成一份专业、详细、可解释的旅行计划。

今天是 {today}。所有涉及日期、星期的计算一律以这个日期为参照。

请严格按照以下 Markdown 格式和规则输出：

---

# {title}

## 约束摘要

{constraints}

## 天气预报与出行提示

（如果下方提供了天气数据，请根据天气情况为每一天给出出行提示和应对建议，
包括是否需要带伞、防晒、调整户外活动等。如果没有天气数据，注明"暂无天气数据"。）

## 行程总览

| 时间 | 地点 | 交通 | 预算 | 为什么这样安排 |
|:---|:---|:---|:--:|:---|
（每一行代表一天的行程概览，共 {total_days} 行）

## 每日详细计划
（每天独立小节，格式见下）

## 预算拆分

| 类别 | 明细 | 预估费用（元） |
|:---|:---|:--:|
（交通、住宿、餐饮、门票、购物等类别）

## 风险与备选方案

| 潜在风险 | 影响 | 备选方案 |
|:---|:---|:---|
（至少列出 3 条风险，必须包含天气相关的风险及其备选方案）

---

**规划规则（必须遵守）：**

1. **标题**：格式为 "# N天M晚目的地旅行计划"。天数根据 start_date 和 end_date 计算。
2. **约束摘要**：将用户偏好中的所有约束条件以条目形式列出。
3. **天气预报与出行提示**：如提供了天气数据，必须参考实际天气为每天做出行提示。
4. **行程总览**：每行代表一天，包含当天主要活动地点、推荐交通方式、当天预算分配、安排逻辑。
5. **每日详细计划**以 "### Day N: YYYY-MM-DD（星期X）" 开头，然后一个表格。
6. **预算拆分**分类合理，总额应在用户预算范围内。
7. **风险**必须包含天气相关风险，每条配具体备选方案。
8. 考虑用户的兴趣标签和必去景点，避开 avoid 中的项目。
9. 交通方式考虑出发地与目的地之间的实际距离和可行方式。
10. 出发那天要考虑从出发地到目的地的交通时间和到达后的安排。
11. 如果提供了用户的历史偏好，请参考历史数据分析。
12. 输出纯 Markdown，不要加额外的解释文字。"""

PLANNER_USER = """请根据以下旅行偏好生成计划。

偏好信息：
{preference_json}

{weather_section}

{history_section}

开始规划。"""

PLANNER_USER_NO_WEATHER = """请根据以下旅行偏好生成计划。

偏好信息：
{preference_json}

（未提供天气数据，请基于历史气候常识给一般性建议。）

{history_section}

开始规划。"""


class TravelPlanGenerator:

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.4,
        )

    def generate(
        self,
        preference: TravelPreference,
        weather_data: Optional[str] = None,
        history_context: Optional[str] = None,
    ) -> str:
        missing = preference.get_missing_fields()
        if missing:
            labels = {"destination": "目的地", "departure": "出发地",
                       "start_date": "出发日期", "end_date": "返程日期"}
            raise ValueError(f"缺少以下必填字段: {', '.join(labels.get(f, f) for f in missing)}")

        title = self._build_title(preference)
        constraints = self._build_constraints_section(preference)
        total_days = self._calculate_days(preference)

        today = date.today().isoformat()
        system_text = PLANNER_SYSTEM.format(title=title, constraints=constraints, total_days=total_days, today=today)
        pref_json = json.dumps(preference.model_dump(exclude_none=True), ensure_ascii=False, indent=2)
        history_section = f"\n{history_context}\n" if history_context else "\n（无历史偏好数据）\n"

        if weather_data:
            user_text = PLANNER_USER.format(
                preference_json=pref_json,
                weather_section=f"天气数据（请严格参考）：\n{weather_data}",
                history_section=history_section,
            )
        else:
            user_text = PLANNER_USER_NO_WEATHER.format(preference_json=pref_json, history_section=history_section)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_text}"),
            ("user", "{user_text}"),
        ])
        chain = prompt | self._llm

        try:
            response = chain.invoke({"system_text": system_text, "user_text": user_text})
            content = response.content if hasattr(response, "content") else str(response)
            if isinstance(content, str) and len(content) > 50:
                return content.strip()
        except Exception:
            pass

        messages = [SystemMessage(content=system_text), HumanMessage(content=user_text)]
        response = self._llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()

    def _build_title(self, pref: TravelPreference) -> str:
        days = self._calculate_days(pref)
        nights = days - 1 if days > 1 else 1
        dest = pref.destination or "未知目的地"
        return f"{days}天{nights}晚{dest}旅行计划"

    @staticmethod
    def _calculate_days(pref: TravelPreference) -> int:
        try:
            start = datetime.strptime(pref.start_date or "", "%Y-%m-%d").date()
            end = datetime.strptime(pref.end_date or "", "%Y-%m-%d").date()
            return (end - start).days + 1
        except (ValueError, TypeError):
            warnings.warn(f"Unable to parse dates: start={pref.start_date}, end={pref.end_date}; defaulting to 1 day")
            return 1

    def _build_constraints_section(self, pref: TravelPreference) -> str:
        labels = {"destination": "目的地", "departure": "出发地", "start_date": "出发日期",
                   "end_date": "返程日期", "budget_range": "预算", "travelers": "人数",
                   "interests": "兴趣", "must_see": "必去", "avoid": "避开",
                   "accommodation_type": "住宿", "transport_preference": "交通"}
        lines = []
        data = pref.model_dump(exclude_none=True)
        for key in TravelPreference.REQUIRED_FIELDS:
            val = data.get(key)
            if val:
                lines.append(f"- {labels[key]}: {val}")
        for key in ["budget_range", "travelers", "interests", "must_see", "avoid", "accommodation_type", "transport_preference"]:
            val = data.get(key)
            if val:
                if isinstance(val, list):
                    if key == "budget_range" and len(val) == 2:
                        lines.append(f"- {labels[key]}: {val[0]:,} - {val[1]:,} 元")
                    else:
                        lines.append(f"- {labels[key]}: {'、'.join(str(v) for v in val)}")
                else:
                    lines.append(f"- {labels[key]}: {val}")
        return "\n".join(lines)
