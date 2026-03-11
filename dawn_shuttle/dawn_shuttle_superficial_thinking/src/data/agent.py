"""记忆智能体"""

import json
from typing import TYPE_CHECKING, Any

from ..core.prompts import (
    ANALYZE_QUERY_PROMPT,
    COMPRESS_MEMORY_PROMPT,
    DIAGNOSE_MEMORY_PROMPT,
    EXTRACT_KEYWORDS_PROMPT,
    EXTRACT_PERSONALITY_PROMPT,
    JUDGE_IMPORTANCE_PROMPT,
    RELATE_MEMORY_PROMPT,
    VALIDATE_MEMORY_PROMPT,
)
from ..core.types import (
    CompressionResult,
    DiagnosisResult,
    FuzzyMemory,
    ImportanceResult,
    Keywords,
    PersonalitySummary,
    PreciseMemory,
    QueryAnalysis,
    ValidationResult,
)

if TYPE_CHECKING:
    from dawn_shuttle_intelligence import LLM


class MemoryAgent:
    """记忆管理智能体"""

    def __init__(
        self,
        llm: "LLM",
        system_prompt: str,
        model: str = "deepseek-v3",
    ) -> None:
        """
        Args:
            llm: LLM 实例（来自 intelligence）
            system_prompt: 主对话的人设/角色设定
            model: 使用的模型名称
        """
        self._llm = llm
        self._system_prompt = system_prompt
        self._model = model
        self._personality: PersonalitySummary | None = None

    @property
    def personality(self) -> PersonalitySummary:
        """获取人设摘要（懒加载，未提取时返回默认值）"""
        if self._personality is None:
            # 返回默认人设
            return PersonalitySummary(
                role="助手",
                expertise=[],
                target_users=[],
                constraints=[],
                valuable_memory_types=[],
                summary=self._system_prompt,
            )
        return self._personality

    async def extract_personality(self) -> PersonalitySummary:
        """从 system_prompt 提取人设摘要"""
        prompt = EXTRACT_PERSONALITY_PROMPT.format(system_prompt=self._system_prompt)

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        self._personality = PersonalitySummary.from_dict(data)
        return self._personality

    # === 校验 ===

    async def validate(self, memory: PreciseMemory) -> ValidationResult:
        """校验记忆是否与人设冲突"""
        prompt = VALIDATE_MEMORY_PROMPT.format(
            personality_summary=self.personality.format_for_prompt(),
            role=memory.role,
            content=memory.content,
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return ValidationResult.from_dict(data)

    # === 重要性判断 ===

    async def judge_importance(
        self,
        new_memory: PreciseMemory,
        existing_summaries: list[str],
    ) -> ImportanceResult:
        """评估记忆重要性"""
        prompt = JUDGE_IMPORTANCE_PROMPT.format(
            personality_summary=self.personality.format_for_prompt(),
            existing_summaries=(
                "\n".join(f"- {s}" for s in existing_summaries)
                if existing_summaries
                else "（暂无已有记忆）"
            ),
            new_role=new_memory.role,
            new_content=new_memory.content,
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return ImportanceResult.from_dict(data)

    # === 关键词提取 ===

    async def extract_keywords(self, content: str) -> Keywords:
        """提取关键词"""
        prompt = EXTRACT_KEYWORDS_PROMPT.format(content=content)

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return Keywords(
            primary=data.get("primary_keywords", []),
            secondary=data.get("secondary_keywords", []),
            entities=data.get("entities", []),
            category=data.get("category", "事实"),
        )

    # === 压缩 ===

    async def compress(
        self,
        memories: list[PreciseMemory],
    ) -> CompressionResult:
        """将多条精准记忆压缩为一条模糊记忆"""
        memories_text = "\n".join(f"[{m.role}] {m.content}" for m in memories)

        prompt = COMPRESS_MEMORY_PROMPT.format(
            personality_summary=self.personality.format_for_prompt(),
            memories=memories_text,
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return CompressionResult.from_dict(data)

    # === 关联判断 ===

    async def relate(
        self,
        new_memory: FuzzyMemory,
        existing_memories: list[FuzzyMemory],
    ) -> list[dict[str, Any]]:
        """判断新记忆与现有记忆的关联"""
        if not existing_memories:
            return []

        existing_text = "\n".join(
            f"ID: {m.id}\n摘要: {m.summary}" for m in existing_memories
        )

        prompt = RELATE_MEMORY_PROMPT.format(
            new_id=new_memory.id,
            new_summary=new_memory.summary,
            existing_memories=existing_text,
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        relations: list[dict[str, Any]] = data.get("relations", [])
        return relations

    # === 查询分析 ===

    async def analyze_query(
        self,
        query: str,
        working_memory: list[PreciseMemory],
        fuzzy_summaries: list[str],
    ) -> QueryAnalysis:
        """分析查询意图"""
        working_text = "\n".join(
            f"[{m.role}] {m.content[:100]}..." for m in working_memory[-5:]
        )
        fuzzy_text = "\n".join(f"- {s}" for s in fuzzy_summaries[:20])

        prompt = ANALYZE_QUERY_PROMPT.format(
            personality_summary=self.personality.format_for_prompt(),
            query=query,
            working_memory=working_text or "（无）",
            fuzzy_summaries=fuzzy_text or "（无）",
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return QueryAnalysis.from_dict(data)

    # === 诊断 ===

    async def diagnose(
        self,
        query: str,
        candidates: list[FuzzyMemory],
    ) -> DiagnosisResult:
        """诊断候选记忆"""
        if not candidates:
            return DiagnosisResult()

        candidates_text = "\n".join(
            f"ID: {m.id}\n摘要: {m.summary}\n关键词: {', '.join(m.keywords.primary)}"
            for m in candidates
        )

        prompt = DIAGNOSE_MEMORY_PROMPT.format(
            query=query,
            candidate_memories=candidates_text,
        )

        response = await self._call_llm(prompt)
        data = self._parse_json_response(response)

        return DiagnosisResult.from_dict(data)

    # === 辅助方法 ===

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        try:
            # 方式1: OpenAICompatibleProvider 风格 (generate 需要 messages 和 config)
            if hasattr(self._llm, "generate"):
                import inspect

                sig = inspect.signature(self._llm.generate)
                params = list(sig.parameters.keys())

                # 如果 generate 需要 messages 和 config 参数
                if "messages" in params and "config" in params:
                    # 动态导入类型
                    from dawn_shuttle.dawn_shuttle_intelligence import (
                        GenerateConfig,
                        Message,
                    )

                    messages = [Message.user(prompt)]
                    config = GenerateConfig(model=self._model)
                    response = await self._llm.generate(messages, config)
                    # 安全检查 response
                    if response is None:
                        raise RuntimeError("LLM returned None response")
                    # 获取文本
                    text = getattr(response, "text", None)
                    if text is None:
                        # 尝试其他属性
                        text = getattr(response, "content", None)
                    if text is None:
                        # 尝试 str 转换
                        text = str(response)
                    return str(text) if text else ""
                else:
                    # 旧风格：直接传 prompt
                    result = await self._llm.generate(prompt)
                    if result is None:
                        raise RuntimeError("LLM returned None result")
                    return str(result)

            # 方式2: chat 方法
            elif hasattr(self._llm, "chat"):
                response = await self._llm.chat([{"role": "user", "content": prompt}])
                if response is None:
                    raise RuntimeError("LLM chat returned None response")
                if hasattr(response, "content"):
                    content = response.content
                    return str(content) if content else ""
                return str(response)

            else:
                raise AttributeError("LLM has no generate or chat method")
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """解析 JSON 响应"""
        # 空响应检查
        if not response or not response.strip():
            raise ValueError("Empty response from LLM")
        
        # 尝试提取 JSON 块
        response = response.strip()

        # 如果有 markdown 代码块，提取内容
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end == -1:
                end = len(response)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end == -1:
                end = len(response)
            response = response[start:end].strip()

        # 尝试找到 JSON 对象
        if response.startswith("{"):
            # 找到匹配的 }
            depth = 0
            end_idx = 0
            for i, c in enumerate(response):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            response = response[:end_idx]

        try:
            result: dict[str, Any] = json.loads(response)
            return result
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON response: {e}\nResponse: {response[:200]}"
            ) from e

    # === 降级方法 ===

    def rule_based_importance(
        self,
        new_memory: PreciseMemory,
        existing_summaries: list[str],
    ) -> ImportanceResult:
        """规则降级判断（不调用 LLM）"""
        score = 0.5

        # 用户消息通常更重要
        if new_memory.role == "user":
            score += 0.1

        # 包含关键词提示重要性
        important_keywords = ["偏好", "喜欢", "决定", "重要", "记住", "总是", "从不"]
        for kw in important_keywords:
            if kw in new_memory.content:
                score += 0.15
                break

        # 内容长度（较长可能包含更多信息）
        if len(new_memory.content) > 200:
            score += 0.1

        # 检查冗余
        if existing_summaries:
            content_lower = new_memory.content.lower()
            for summary in existing_summaries:
                # 简单的文本重叠检查
                overlap = sum(
                    1 for word in content_lower.split() if word in summary.lower()
                )
                if overlap > 3:
                    score -= 0.2
                    break

        return ImportanceResult(
            importance=min(max(score, 0.0), 1.0),
            persona_relevance=0.5,
            novelty=0.5,
            redundancy=0.0,
            action="add",
            reason="降级规则判断",
        )
