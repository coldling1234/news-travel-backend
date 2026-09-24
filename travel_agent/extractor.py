"""偏好提取器 — 自然语言 → 结构化 TravelPreference，含三层降级解析。"""
"""Preference extraction from natural language using LLM + structured output."""

import json
from datetime import date
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from .config import settings
from .models.preference import TravelPreference


EXTRACTION_SYSTEM_TEXT = """你是一个旅行偏好分析助手。你的任务是从用户的自然语言输入中提取结构化的旅行偏好信息。

今天是 {today}。请以此为参照，将相对日期（如"下周五"、"八月中旬"、"月底"）转换为具体的 YYYY-MM-DD 格式。
例如，如果今天是 2026-07-09（周四）：
- "下周五" → 2026-07-17
- "下周一" → 2026-07-13
- "月底" → 2026-07-31
- "8月中旬" → 2026-08-15

对于预算，提取人民币数值范围：[min, max]。如"一万以内"→ [0, 10000]，"两三千"→ [2000, 3000]。
对于人数，如"我和我老婆"→ 2，"一家三口"→ 3。
对于没有提到的字段，不要编造，直接省略（不包含该 JSON 键）。"""

EXTRACTION_WITH_CONTEXT_SYSTEM = """你是一个旅行偏好分析助手。你的任务是从用户的新回复中提取额外的偏好信息。

今天是 {today}。请以此为参照，将相对日期转换为具体的 YYYY-MM-DD 格式。

在下方的 JSON 中，一些字段已经有值（已标注"已填写"），一些字段为 null（标注"缺失"）。
请只从用户新回复中提取信息来填充缺失的字段，已填写的字段不要改动。
用户没有新提供信息的缺失字段，保持为 null。"""


class PreferenceExtractor:
    """偏好提取器 — 自然语言 → 结构化 TravelPreference。

    使用 DeepSeek LLM + PydanticOutputParser 逐层降级：
    1. 首选：PydanticOutputParser 解析结构化输出
    2. 降级：手动 JSON 解析（去除 markdown 代码块）
    3. 最终：要求 LLM 修正输出格式后重试
    """
    """Extract structured TravelPreference from natural language input."""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.1,
        )
        self._parser = PydanticOutputParser(pydantic_object=TravelPreference)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, user_input: str) -> TravelPreference:
        """从新的自然语言输入中提取偏好（首次提取）。"""
        today = date.today().isoformat()
        system_text = EXTRACTION_SYSTEM_TEXT.format(today=today)
        format_instructions = self._parser.get_format_instructions()
        full_user_text = f"{user_input}\n\n{format_instructions}"
        return self._invoke_llm(system_text, full_user_text)

    def extract_with_context(
        self, user_input: str, existing: TravelPreference
    ) -> TravelPreference:
        """从用户追问回复中增量提取。

        只补充缺失字段，不会覆盖已有值。
        """
        today = date.today().isoformat()
        system_text = EXTRACTION_WITH_CONTEXT_SYSTEM.format(today=today)
        format_instructions = self._parser.get_format_instructions()

        # Build a diff view: show filled vs missing fields
        pref_data = existing.model_dump()
        annotated: dict[str, object] = {}
        missing = set(existing.get_missing_fields())
        for key, val in pref_data.items():
            if key in TravelPreference.REQUIRED_FIELDS:
                annotated[key] = None if key in missing else val
        existing_json = json.dumps(annotated, ensure_ascii=False, indent=2)

        full_user_text = (
            f"当前偏好（null = 缺失，需补充）：\n{existing_json}\n\n"
            f"用户新回复：{user_input}\n\n"
            f"请只从新回复中提取信息填充 null 字段，已填字段不要改动。\n\n"
            f"{format_instructions}"
        )
        return self._invoke_llm(system_text, full_user_text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _invoke_llm(self, system_text: str, user_text: str) -> TravelPreference:
        """调用 LLM 并解析输出（含三层降级策略）。

        Phase 1: 尝试 PydanticOutputParser 结构化解析
        Phase 2: 如果 Phase 1 失败，手动解析 JSON
        Phase 3: 如果 Phase 2 失败，要求 LLM 修正格式后重试
        """
        messages = [
            SystemMessage(content=system_text),
            HumanMessage(content=user_text),
        ]

        try:
            response = self._llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parser.parse(content)
        except Exception as first_err:
            # Fallback 1: strip code fences and retry with parser
            content = response.content if hasattr(response, "content") else str(response)
            try:
                return self._parse_json_string(content)
            except Exception:
                # Fallback 2: ask LLM to fix its own output
                fix_messages = [
                    SystemMessage(content=system_text),
                    HumanMessage(content=user_text),
                    SystemMessage(content=(
                        "你上一次的输出格式不正确，无法被 JSON 解析器解析。"
                        "请只输出一个纯 JSON 对象，不要包含任何 markdown 标记、"
                        "解释文字或额外内容。"
                    )),
                ]
                response2 = self._llm.invoke(fix_messages)
                content2 = response2.content if hasattr(response2, "content") else str(response2)
                return self._parse_json_string(content2)

    @staticmethod
    def _parse_json_string(content: str) -> TravelPreference:
        """从 LLM 的回复文本中提取和解析 JSON。

        自动处理 markdown 代码块包裹的情况。
        """
        text = content.strip()
        if text.startswith("```"):
            text = text[text.index("\n") + 1:] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
        return TravelPreference(**data)
