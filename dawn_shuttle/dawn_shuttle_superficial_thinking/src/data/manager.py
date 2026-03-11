"""记忆管理器 - 统一入口"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Literal

from ..core.config import DEFAULT_CONFIG, MemoryConfig
from ..core.types import (
    CompressionResult,
    FuzzyMemory,
    PreciseMemory,
    RetrievalResult,
)
from ..db.storage import PersistentStorage
from .agent import MemoryAgent
from .async_index import AsyncKeywordIndex
from .fuzzy import FuzzyMemoryGraph
from .working import WorkingMemory

if TYPE_CHECKING:
    from dawn_shuttle_intelligence import LLM

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器 - 统一入口"""

    def __init__(
        self,
        llm: "LLM",
        system_prompt: str,
        config: MemoryConfig | None = None,
        model: str = "deepseek-v3",
    ):
        """
        Args:
            llm: intelligence 的 LLM 实例
            system_prompt: 主对话的人设
            config: 配置项
            model: 使用的模型名称
        """
        self._config = config or DEFAULT_CONFIG
        self._llm = llm
        self._system_prompt = system_prompt
        self._model = model

        # 初始化组件
        self._agent = MemoryAgent(llm, system_prompt, model)
        self._working = WorkingMemory(self._config)
        self._fuzzy = FuzzyMemoryGraph(self._config)
        self._index = AsyncKeywordIndex()

        # 延迟初始化存储（避免循环导入）
        self._storage: PersistentStorage | None = None

        # 状态
        self._message_count = 0
        self._initialized = False
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def initialize(self) -> "MemoryManager":
        """初始化（提取人设、加载持久化数据）"""
        if self._initialized:
            return self

        # 初始化存储
        from ..db.storage import PersistentStorage

        self._storage = PersistentStorage(self._config)

        # 提取人设摘要
        try:
            await self._agent.extract_personality()
            logger.info("Personality extracted successfully")
        except Exception as e:
            logger.warning(f"Failed to extract personality: {e}")

        # 加载持久化数据
        try:
            await self._load_from_storage()
            logger.info("Loaded memories from storage")
        except Exception as e:
            logger.warning(f"Failed to load from storage: {e}")

        self._initialized = True
        return self

    # === 写入操作 ===

    async def add_message(
        self,
        role: Literal["user", "assistant", "system"],
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._ensure_initialized()

        # 1. 创建精准记忆
        precise = PreciseMemory(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        # 2. 规则评估重要性（不调用 LLM）
        precise.importance = self._rule_importance(precise)

        # 3. 添加到工作记忆
        evicted = self._working.add(precise)

        # 4. 保存到持久化
        if self._storage:
            self._storage.save_message(precise)

        # 5. 批量压缩被淘汰的记忆
        if evicted:
            await self._batch_compress()

        self._message_count += 1

        # 6. 定期保存
        if (
            self._config.auto_save
            and self._message_count % self._config.save_interval == 0
        ):
            self._start_background_task(self._save_async())

    async def add_messages(self, messages: list[dict[str, Any]]) -> None:
        """批量添加消息"""
        for msg in messages:
            await self.add_message(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                metadata=msg.get("metadata"),
            )

    def _create_fuzzy_memory(
        self,
        sources: list[PreciseMemory],
        compression: CompressionResult,
    ) -> FuzzyMemory:
        """创建模糊记忆"""
        avg_importance = sum(m.importance for m in sources) / len(sources)

        return FuzzyMemory(
            summary=compression.summary,
            triples=compression.triples,
            keywords=compression.keywords,
            weight=1.0,
            importance=avg_importance,
            source_ids=[m.id for m in sources],
        )

    # === 读取操作 ===

    async def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        await self._ensure_initialized()

        if top_k is None:
            top_k = self._config.retrieval_top_k

        # 简单关键词提取（无 LLM）
        keywords = self._extract_keywords(query)

        if not keywords:
            return RetrievalResult(reason="No keywords extracted from query")

        # 关键词搜索
        scored = await self._index.search_with_score(primary_keywords=keywords)

        if not scored:
            return RetrievalResult(reason="No matching memories found")

        # 返回 top_k 结果
        results = []
        for mem_id, _ in scored[:top_k]:
            mem = self._fuzzy.get(mem_id)
            if mem:
                mem.touch()
                self._fuzzy.touch(mem_id)
                results.append(mem)

        return RetrievalResult(
            fuzzy_memories=results,
            confidence=0.7,
            reason="Retrieved by keyword matching",
        )

    def get_context(self, include_fuzzy: bool = True) -> list[dict[str, str]]:
        """
        获取当前上下文（用于 LLM）

        Args:
            include_fuzzy: 是否包含模糊记忆摘要
        """
        context = self._working.get_context()

        if include_fuzzy and self._fuzzy:
            summaries = self._fuzzy.get_summaries()
            if summaries:
                memory_context = "【历史记忆摘要】\n" + "\n".join(
                    f"- {s}" for s in summaries[:10]
                )
                context.insert(0, {"role": "system", "content": memory_context})

        return context

    # === 状态操作 ===

    def get_stats(self) -> dict[str, Any]:
        """获取记忆系统状态"""
        return {
            "working_count": len(self._working),
            "working_tokens": self._working.total_tokens,
            "fuzzy_count": len(self._fuzzy),
            "message_count": self._message_count,
            "initialized": self._initialized,
        }

    async def decay(self) -> None:
        """手动触发权重衰减"""
        self._fuzzy.decay_weights()

        # 持久化更新
        if self._storage:
            for mem in self._fuzzy.get_all_memories():
                self._storage.update_fuzzy_access(
                    mem.id,
                    mem.last_accessed.isoformat(),
                    mem.access_count,
                    mem.weight,
                )

    def clear_working(self) -> None:
        """清空工作记忆（保留持久化）"""
        self._working.clear()

    # === 持久化操作 ===

    async def save(self) -> None:
        """保存所有状态到磁盘"""
        await self._save_async()

    async def _save_async(self) -> None:
        """异步保存"""
        if not self._storage:
            return

        # 保存模糊记忆
        for mem in self._fuzzy.get_all_memories():
            self._storage.save_fuzzy(mem)

        logger.debug("Memory state saved")

    async def _load_from_storage(self) -> None:
        """从存储加载数据"""
        if not self._storage:
            return

        # 加载模糊记忆
        fuzzy_memories = self._storage.load_all_fuzzy()
        for mem in fuzzy_memories:
            self._fuzzy.add(mem)
            await self._index.add(mem.id, mem.keywords)

        # 加载边
        edges = self._storage.load_all_edges()
        for edge in edges:
            self._fuzzy.add_edge(edge)

        logger.info(f"Loaded {len(fuzzy_memories)} fuzzy memories")

    async def close(self) -> None:
        """关闭并清理资源"""
        # 等待后台任务
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # 保存数据
        await self._save_async()

        # 关闭存储
        if self._storage:
            self._storage.close()

    # === 辅助方法 ===

    async def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            await self.initialize()

    def _start_background_task(self, coro: Coroutine[Any, Any, Any]) -> None:
        """启动后台任务"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _rule_importance(self, memory: PreciseMemory) -> float:
        """规则评估重要性（不调用 LLM）"""
        score = 0.5

        # 用户消息更重要
        if memory.role == "user":
            score += 0.2

        # 包含偏好关键词
        preference_keywords = ["喜欢", "偏好", "我是", "我会", "我的", "擅长", "习惯"]
        if any(kw in memory.content for kw in preference_keywords):
            score += 0.2

        # 消息长度
        if len(memory.content) > 100:
            score += 0.1

        # 包含问题
        if "？" in memory.content or "?" in memory.content:
            score += 0.1

        return min(score, 1.0)

    async def _batch_compress(self) -> None:
        """批量压缩工作记忆（一次 LLM 调用）"""
        """批量压缩工作记忆（一次 LLM 调用）"""
        # 获取所有工作记忆
        memories = self._working.get_memories()
        if not memories:
            return

        # 批量压缩
        try:
            compression = await self._agent.compress(memories)
            fuzzy = self._create_fuzzy_memory(memories, compression)

            # 添加到模糊记忆图
            evicted_fuzzy = self._fuzzy.add(fuzzy)

            # 更新索引
            await self._index.add(fuzzy.id, fuzzy.keywords)

            # 保存到持久化
            if self._storage:
                self._storage.save_fuzzy(fuzzy)
                if evicted_fuzzy:
                    self._storage.delete_fuzzy(evicted_fuzzy.id)

            logger.info(f"Batch compressed {len(memories)} memories into fuzzy memory")

        except Exception as e:
            logger.error(f"Batch compression failed: {e}")

    def _extract_keywords(self, query: str) -> list[str]:
        """简单关键词提取（不调用 LLM）"""
        # 移除常见停用词
        stopwords = {
            "的",
            "是",
            "了",
            "我",
            "你",
            "他",
            "她",
            "它",
            "们",
            "这",
            "那",
            "有",
            "在",
            "不",
            "就",
            "也",
            "都",
            "会",
            "能",
            "要",
            "可以",
            "什么",
            "怎么",
            "为什么",
            "哪",
            "吗",
            "呢",
            "啊",
            "吧",
            "哦",
            "嗯",
        }

        # 简单分词（按空格和标点）
        import re

        words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", query)

        # 过滤
        keywords = []
        for w in words:
            if len(w) >= 2 and w not in stopwords:
                keywords.append(w)

        return keywords[:5]  # 最多返回 5 个关键词

    async def query_memory(self, query: str) -> str:
        """记忆查询工具（LLM 调用）

        这是给 LLM 调用的工具，用于按需查询记忆。
        会调用 LLM 进行意图分析和结果汇总。"""
        """记忆查询工具（LLM 调用）

    这是给 LLM 调用的工具，用于按需查询记忆。
    会调用 LLM 进行意图分析和结果汇总。

    Args:
        query: 查询问题

    Returns:
        汇总后的流畅语段
    """
        await self._ensure_initialized()

        # 1. LLM 分析查询意图
        analysis = await self._agent.analyze_query(
            query,
            self._working.get_memories(),
            self._fuzzy.get_summaries(),
        )

        if not analysis.need_memory:
            return "当前查询不需要历史记忆。"

        # 2. 检索相关记忆
        scored = await self._index.search_with_score(
            primary_keywords=analysis.keywords,
            secondary_keywords=analysis.related_keywords,
        )

        if not scored:
            return "未找到相关记忆。"

        # 3. 获取记忆内容
        memories = []
        for mem_id, _ in scored[:10]:
            mem = self._fuzzy.get(mem_id)
            if mem:
                memories.append(f"- {mem.summary}")

        # 4. LLM 汇总
        summary_prompt = f"""请将以下记忆片段汇总成一段流畅的文字，回答用户的问题：{query}

    记忆片段：
    {chr(10).join(memories)}

    要求：
    1. 保持信息准确
    2. 语言自然流畅
    3. 突出与问题相关的内容
    """

        result = await self._agent._call_llm(summary_prompt)
        return result


async def initialize(
    llm: "LLM",
    system_prompt: str,
    config: MemoryConfig | None = None,
    model: str = "deepseek-v3",
) -> MemoryManager:
    """初始化记忆管理器的便捷函数"""
    manager = MemoryManager(llm, system_prompt, config, model)
    return await manager.initialize()
