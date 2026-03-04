"""工作记忆"""

import re
from collections import deque
from typing import Any

from ..core.config import MemoryConfig
from ..core.types import PreciseMemory


def count_tokens(text: str) -> int:
    """
    简单 token 计数（估算）

    规则：
    - 英文：约 4 字符 = 1 token
    - 中文：约 1.5 字符 = 1 token
    """
    if not text:
        return 0

    # 分离中英文
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[a-zA-Z0-9]", text))
    other = len(text) - chinese - english

    return max(1, int(chinese / 1.5 + english / 4 + other / 3))


class WorkingMemory:
    """工作记忆 - 内存中的消息队列"""

    def __init__(self, config: MemoryConfig):
        self._config = config
        self._queue: deque[PreciseMemory] = deque()
        self._current_tokens = 0

    @property
    def total_tokens(self) -> int:
        """当前总 token 数"""
        return self._current_tokens

    def add(self, memory: PreciseMemory) -> PreciseMemory | None:
        """
        添加记忆，返回被淘汰的记忆（如有）

        淘汰条件：
        1. 消息数量超过 max_messages
        2. 总 token 数超过 max_tokens
        """
        # 计算 token
        if memory.token_count == 0:
            memory.token_count = count_tokens(memory.content)

        self._queue.append(memory)
        self._current_tokens += memory.token_count

        # 检查并淘汰
        evicted = None
        while self._should_evict():
            evicted = self._queue.popleft()
            self._current_tokens -= evicted.token_count

        return evicted

    def _should_evict(self) -> bool:
        """判断是否需要淘汰"""
        return (
            len(self._queue) > self._config.working_max_messages
            or self._current_tokens > self._config.working_max_tokens
        )

    def get_context(self) -> list[dict[str, str]]:
        """获取用于 LLM 的上下文格式"""
        return [m.to_message() for m in self._queue]

    def get_memories(self) -> list[PreciseMemory]:
        """获取所有精准记忆"""
        return list(self._queue)

    def get_last_n(self, n: int) -> list[PreciseMemory]:
        """获取最近 N 条记忆"""
        return list(self._queue)[-n:]

    def is_full(self) -> bool:
        """检查是否达到容量上限"""
        return (
            len(self._queue) >= self._config.working_max_messages
            or self._current_tokens >= self._config.working_max_tokens
        )

    def clear(self) -> list[PreciseMemory]:
        """清空并返回所有记忆"""
        memories = list(self._queue)
        self._queue.clear()
        self._current_tokens = 0
        return memories

    def __len__(self) -> int:
        return len(self._queue)

    def __bool__(self) -> bool:
        return len(self._queue) > 0

    def stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "message_count": len(self._queue),
            "total_tokens": self._current_tokens,
            "max_messages": self._config.working_max_messages,
            "max_tokens": self._config.working_max_tokens,
        }
