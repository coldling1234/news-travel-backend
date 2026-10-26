"""ReAct Agent — LLM 自主选择工具完成旅行规划。"""

from datetime import date

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from config.settings import settings
from .pii_masking import PIIMaskingHandler
from .tools import (
    collect_preferences,
    search_places,
    geocode_location,
    estimate_route,
    get_weather,
    estimate_budget,
    plan_trip,
    score_hotels,
    score_routes,
)


TRAVEL_AGENT_SYSTEM_PROMPT = """你是一个专业的 AI 旅行规划助手。

## 当前时间

今天是 {today}。回答涉及日期、星期、相对日期、天气预报时段等问题时，一律以这个日期为参照，不要使用训练数据中的旧年份。

## 你可以使用的工具

1. **collect_preferences** — 从用户的自然语言中提取结构化偏好。
   如果返回的 missing_fields 不为空，说明信息不完整，需要向用户追问。

2. **search_places** — 搜索景点、餐厅、酒店。
   当需要推荐具体地点时调用。

3. **geocode_location** — 地名转经纬度坐标。

4. **estimate_route** — 估算两地之间的路程和交通方式。

5. **get_weather** — 查询目的地天气预报。

6. **estimate_budget** — 估算旅行各项费用（区间估算）。

7. **score_hotels** — 对候选酒店按评分/口碑、位置便利性、安静度打分排序。
   在推荐酒店前调用，并把 search_places 返回的 JSON 原样传入。

8. **score_routes** — 对候选路线按耗时、距离、换乘次数、费用打分排序。
   在推荐路线前调用，并把 estimate_route 返回的 JSON 原样传入。

9. **plan_trip** — 根据已收集的偏好生成完整的 Markdown 旅行计划。
   只有当所有必要信息都已收集完毕后才调用。

## 工作流程

1. **收集偏好**：首先调用 collect_preferences 提取用户需求。
   如果返回有 missing_fields，礼貌地向用户追问缺失的信息。

2. **补充信息**：根据用户偏好，调用 search_places、get_weather、estimate_budget 等工具丰富行程。

3. **评分排序**：推荐酒店前调用 score_hotels，推荐路线前调用 score_routes，
   并根据返回的排名和分数向用户解释推荐理由。

4. **生成计划**：当所有必要信息齐备后，调用 plan_trip 生成最终旅行计划。

5. **展示计划**：将生成的 Markdown 计划原样展示给用户。

## 重要规则

- 不要一次性调用所有工具。每次只调用当前步骤需要的工具。
- 如果用户提供的信息不完整，先追问再继续。
- 推荐酒店或路线前，必须先调用对应的评分工具。
- 追问和最终回答都使用中文。
"""


def create_travel_agent():
    """创建并返回一个已配置好所有工具的 ReAct 旅行规划 Agent。"""
    llm = ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=0.2,
        callbacks=[PIIMaskingHandler()],
    )

    tools = [
        collect_preferences,
        search_places,
        geocode_location,
        estimate_route,
        get_weather,
        estimate_budget,
        plan_trip,
        score_hotels,
        score_routes,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=TRAVEL_AGENT_SYSTEM_PROMPT.format(today=date.today().isoformat()),
    )

    return agent


_agent = None


def get_agent():
    """获取全局 Agent 单例（懒加载）。"""
    global _agent
    if _agent is None:
        _agent = create_travel_agent()
    return _agent
