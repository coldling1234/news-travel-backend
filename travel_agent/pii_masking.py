"""PII 敏感信息脱敏中间件 — 基于 LangChain CallbackHandler。

在 LLM 调用前拦截 prompt，将有损脱敏敏感信息（姓名、身份证号、
手机号、银行卡号、邮箱等），替换为占位符。LLM 只看到占位符，
真实值不离开本地。
"""

import re
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage


class PIIMaskingHandler(BaseCallbackHandler):
    """在 LLM 调用前拦截消息，执行有损 PII 脱敏。"""

    _PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\b\d{17}[\dXx]\b"), "[身份证号]"),
        (re.compile(r"\b\d{16,19}\b"), "[银行卡号]"),
        (re.compile(r"\b1[3-9]\d{9}\b"), "[手机号]"),
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[邮箱]"),
    ]

    _NAME_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"(?<=我(?:叫|是))[\u4e00-\u9fa5]{2,4}"), "[姓名]"),
        (re.compile(r"(?<=姓名(?:是|为|[:：]))[\u4e00-\u9fa5]{2,4}"), "[姓名]"),
        (re.compile(r"(?<=名字(?:叫|是))[\u4e00-\u9fa5]{2,4}"), "[姓名]"),
    ]

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[Any],
        **kwargs: Any,
    ) -> None:
        self._mask_messages(messages)

    def _mask_messages(self, messages: Any) -> None:
        if isinstance(messages, (list, tuple)):
            for item in messages:
                self._mask_messages(item)
        elif isinstance(messages, BaseMessage):
            self._mask_message(messages)

    def _mask_message(self, msg: BaseMessage) -> None:
        content = msg.content
        if isinstance(content, str):
            masked = self.mask(content)
            if masked != content:
                msg.content = masked

    @classmethod
    def mask(cls, text: str) -> str:
        for pattern, placeholder in cls._PATTERNS:
            text = pattern.sub(placeholder, text)
        for pattern, placeholder in cls._NAME_PATTERNS:
            text = pattern.sub(placeholder, text)
        return text

    @classmethod
    def detect(cls, text: str) -> list[str]:
        """检测敏感信息类型，返回去重后的占位符列表。"""
        found = []
        for pattern, placeholder in cls._PATTERNS:
            if pattern.search(text):
                found.append(placeholder)
        for pattern, placeholder in cls._NAME_PATTERNS:
            if pattern.search(text):
                found.append(placeholder)
        return list(dict.fromkeys(found))
