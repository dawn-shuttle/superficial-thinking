"""关键词索引 - 异步版本"""

import asyncio
from collections import defaultdict
from typing import Any

from ..core.types import Keywords


class AsyncKeywordIndex:
    """关键词倒排索引（异步版本）

    用于并发场景，使用 asyncio.Lock 保护。
    兼容 Python 3.13+ 自由线程模式。
    """

    def __init__(self) -> None:
        self._index: dict[str, set[str]] = defaultdict(set)
        self._category_index: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def add(self, memory_id: str, keywords: Keywords) -> None:
        """添加记忆到索引"""
        async with self._lock:
            for kw in keywords.all_keywords():
                self._index[kw].add(memory_id)

            if keywords.category:
                self._category_index[keywords.category].add(memory_id)

    async def remove(self, memory_id: str, keywords: Keywords) -> None:
        """从索引中移除记忆"""
        async with self._lock:
            for kw in keywords.all_keywords():
                self._index[kw].discard(memory_id)
                if not self._index[kw]:
                    del self._index[kw]

            if keywords.category:
                self._category_index[keywords.category].discard(memory_id)
                if not self._category_index[keywords.category]:
                    del self._category_index[keywords.category]

    async def search(
        self,
        keywords: list[str],
        categories: list[str] | None = None,
    ) -> list[str]:
        """搜索包含任一关键词的记忆ID"""
        async with self._lock:
            result: set[str] = set()

            for kw in keywords:
                if kw in self._index:
                    result.update(self._index[kw])

            if categories:
                category_set: set[str] = set()
                for cat in categories:
                    if cat in self._category_index:
                        category_set.update(self._category_index[cat])
                result &= category_set

            return list(result)

    async def search_with_score(
        self,
        primary_keywords: list[str],
        secondary_keywords: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """带评分的搜索"""
        async with self._lock:
            scores: dict[str, float] = defaultdict(float)

            # 主关键词匹配（权重 1.0）
            for kw in primary_keywords:
                if kw in self._index:
                    for mem_id in self._index[kw]:
                        scores[mem_id] += 1.0
                else:
                    # 部分匹配
                    for idx_kw in self._index:
                        if kw in idx_kw or idx_kw in kw:
                            for mem_id in self._index[idx_kw]:
                                scores[mem_id] += 0.8

            # 扩展关键词匹配（权重 0.5）
            if secondary_keywords:
                for kw in secondary_keywords:
                    if kw in self._index:
                        for mem_id in self._index[kw]:
                            scores[mem_id] += 0.5
                    else:
                        for idx_kw in self._index:
                            if kw in idx_kw or idx_kw in kw:
                                for mem_id in self._index[idx_kw]:
                                    scores[mem_id] += 0.3

            # 分类过滤
            if categories:
                category_set: set[str] = set()
                for cat in categories:
                    if cat in self._category_index:
                        category_set.update(self._category_index[cat])
                if category_set:
                    scores = {k: v for k, v in scores.items() if k in category_set}

            return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    async def get_keywords_for_memory(self, memory_id: str) -> list[str]:
        """获取某记忆的所有关键词"""
        async with self._lock:
            return [kw for kw, ids in self._index.items() if memory_id in ids]

    async def clear(self) -> None:
        """清空索引"""
        async with self._lock:
            self._index.clear()
            self._category_index.clear()

    async def stats(self) -> dict[str, Any]:
        """获取索引统计信息"""
        async with self._lock:
            return {
                "keyword_count": len(self._index),
                "category_count": len(self._category_index),
                "total_memories": len(
                    set().union(*self._index.values()) if self._index else set()
                ),
            }
