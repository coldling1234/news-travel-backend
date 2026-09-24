"""偏好提取与摘要 — 从自然语言一次性提取结构化偏好并生成摘要。"""

from .extractor import PreferenceExtractor
from .summarizer import ConstraintSummarizer
from .models.preference import TravelPreference


class PreferencePipeline:
    """偏好提取与摘要流水线。

    使用方式::

        pipeline = PreferencePipeline()
        pref, summary = pipeline.run_one_shot("我想去北京玩三天")
    """

    def __init__(self) -> None:
        self._extractor = PreferenceExtractor()
        self._summarizer = ConstraintSummarizer()

    def run_one_shot(self, nl_input: str) -> tuple[TravelPreference, str]:
        """单次提取（不追问），用于 @tool 语境。"""
        preference = self._extractor.extract(nl_input)
        summary = self._summarizer.summarize(preference)
        return preference, summary
