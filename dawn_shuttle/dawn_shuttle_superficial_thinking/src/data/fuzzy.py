"""模糊记忆图"""

import math
from collections import deque
from datetime import datetime
from typing import Any

from ..core.config import MemoryConfig
from ..core.types import FuzzyMemory, MemoryEdge, RelationType


class FuzzyMemoryGraph:
    """模糊记忆图 - 内存中的图结构"""

    def __init__(self, config: MemoryConfig):
        self._config = config
        self._nodes: dict[str, FuzzyMemory] = {}
        self._edges: dict[str, list[MemoryEdge]] = {}  # 邻接表：source_id -> edges

    # === 节点操作 ===

    def add(self, memory: FuzzyMemory) -> FuzzyMemory | None:
        """
        添加模糊记忆节点，返回被淘汰的节点（如有）
        """
        evicted = None

        # 检查是否需要淘汰
        while len(self._nodes) >= self._config.fuzzy_max_nodes:
            evicted = self._evict()

        self._nodes[memory.id] = memory
        if memory.id not in self._edges:
            self._edges[memory.id] = []

        return evicted

    def get(self, memory_id: str) -> FuzzyMemory | None:
        """获取节点"""
        return self._nodes.get(memory_id)

    def remove(self, memory_id: str) -> FuzzyMemory | None:
        """移除节点"""
        if memory_id not in self._nodes:
            return None

        node = self._nodes.pop(memory_id)

        # 移除相关边
        if memory_id in self._edges:
            del self._edges[memory_id]

        # 移除指向该节点的边
        for edges in self._edges.values():
            edges[:] = [e for e in edges if e.target_id != memory_id]

        return node

    def _evict(self) -> FuzzyMemory | None:
        """
        淘汰策略：综合权重

        score = weight × importance × access_factor
        """
        min_score = float("inf")
        evict_candidate = None

        for node in self._nodes.values():
            access_factor = 1 + 0.1 * math.log(node.access_count + 1)
            score = node.weight * node.importance * access_factor

            if score < min_score:
                min_score = score
                evict_candidate = node

        if evict_candidate:
            return self.remove(evict_candidate.id)

        return None

    # === 边操作 ===

    def relate(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0,
    ) -> MemoryEdge | None:
        """建立关联边"""
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        edge = MemoryEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
        )

        if source_id not in self._edges:
            self._edges[source_id] = []
        self._edges[source_id].append(edge)

        return edge

    def add_edge(self, edge: MemoryEdge) -> None:
        """添加边"""
        if edge.source_id not in self._edges:
            self._edges[edge.source_id] = []
        self._edges[edge.source_id].append(edge)

    def get_edges(self, memory_id: str) -> list[MemoryEdge]:
        """获取节点的所有出边"""
        return self._edges.get(memory_id, [])

    # === 查询操作 ===

    def get_summaries(self) -> list[str]:
        """获取所有记忆摘要"""
        return [m.summary for m in self._nodes.values()]

    def get_all_memories(self) -> list[FuzzyMemory]:
        """获取所有记忆"""
        return list(self._nodes.values())

    def get_neighbors(
        self,
        memory_id: str,
        depth: int = 2,
        relation_types: list[RelationType] | None = None,
    ) -> list[FuzzyMemory]:
        """
        获取关联记忆（BFS 遍历）

        Args:
            memory_id: 起始记忆ID
            depth: 遍历深度
            relation_types: 只跟随指定类型的边
        """
        if memory_id not in self._nodes:
            return []

        visited = {memory_id}
        result = []
        queue = deque([(memory_id, 0)])

        while queue:
            current_id, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            for edge in self._edges.get(current_id, []):
                # 过滤关系类型
                if relation_types and edge.relation not in relation_types:
                    continue

                neighbor_id = edge.target_id
                if neighbor_id not in visited and neighbor_id in self._nodes:
                    visited.add(neighbor_id)
                    result.append(self._nodes[neighbor_id])
                    queue.append((neighbor_id, current_depth + 1))

        return result

    def search_by_keywords(
        self,
        keywords: list[str],
        top_k: int = 10,
    ) -> list[FuzzyMemory]:
        """通过关键词搜索"""
        results: list[tuple[FuzzyMemory, int]] = []

        for node in self._nodes.values():
            score = self._calculate_keyword_score(node, keywords)
            if score > 0:
                results.append((node, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results[:top_k]]

    def _calculate_keyword_score(
        self,
        memory: FuzzyMemory,
        keywords: list[str],
    ) -> int:
        """计算关键词匹配分数"""
        score = 0
        all_keywords = set(memory.keywords.all_keywords())

        for kw in keywords:
            if kw in memory.keywords.primary:
                score += 3  # 主关键词匹配
            elif kw in memory.keywords.secondary:
                score += 2  # 扩展关键词匹配
            elif kw in memory.keywords.entities:
                score += 2  # 实体匹配
            elif kw in all_keywords:
                score += 1  # 其他匹配

        return score

    # === 权重衰减 ===

    def decay_weights(self, lambda_: float | None = None) -> None:
        """
        权重衰减

        公式: w(t) = w₀ × exp(-λ × Δt)
        """
        if lambda_ is None:
            lambda_ = self._config.fuzzy_decay_lambda

        now = datetime.now()
        for node in self._nodes.values():
            delta_hours = (now - node.last_accessed).total_seconds() / 3600
            node.weight *= math.exp(-lambda_ * delta_hours)

    # === 访问更新 ===

    def touch(self, memory_id: str) -> None:
        """更新访问时间和计数"""
        if memory_id in self._nodes:
            self._nodes[memory_id].touch()

    # === 统计 ===

    def __len__(self) -> int:
        return len(self._nodes)

    def __bool__(self) -> bool:
        return len(self._nodes) > 0

    def stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total_edges = sum(len(edges) for edges in self._edges.values())
        avg_weight = (
            sum(m.weight for m in self._nodes.values()) / len(self._nodes)
            if self._nodes
            else 0
        )

        return {
            "node_count": len(self._nodes),
            "edge_count": total_edges,
            "avg_weight": avg_weight,
            "max_nodes": self._config.fuzzy_max_nodes,
        }
