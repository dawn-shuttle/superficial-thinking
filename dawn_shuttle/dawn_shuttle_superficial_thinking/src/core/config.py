"""配置类定义"""

from dataclasses import dataclass


@dataclass
class MemoryConfig:
    """记忆系统配置"""

    # === 工作记忆 ===
    working_max_messages: int = 20
    """工作记忆最大消息数量"""

    working_max_tokens: int = 4000
    """工作记忆最大 token 数量"""

    # === 模糊记忆 ===
    fuzzy_max_nodes: int = 100
    """模糊记忆图最大节点数"""

    fuzzy_decay_lambda: float = 0.01
    """权重衰减率 λ"""

    # === 人设相关 ===
    personality_update_interval: int = 100
    """人设摘要重新提取间隔（消息数）"""

    # === 检索 ===
    retrieval_top_k: int = 10
    """最终返回的记忆数量"""

    retrieval_candidates: int = 20
    """候选记忆数量（送入 LLM 诊断）"""

    retrieval_threshold: float = 0.3
    """相关性阈值"""

    # === 持久化 ===
    db_path: str = "memory.db"
    """数据库文件路径"""

    auto_save: bool = True
    """是否自动保存"""

    save_interval: int = 10
    """自动保存间隔（消息数）"""

    # === 压缩 ===
    compress_batch_size: int = 5
    """压缩批大小（多少条精准记忆压缩为一条模糊记忆）"""

    # === 其他 ===
    enable_validation: bool = True
    """是否启用记忆校验"""

    enable_conflict_detection: bool = True
    """是否启用冲突检测"""

    def __post_init__(self) -> None:
        """参数校验"""
        if self.working_max_messages < 1:
            raise ValueError("working_max_messages must be >= 1")
        if self.working_max_tokens < 100:
            raise ValueError("working_max_tokens must be >= 100")
        if self.fuzzy_max_nodes < 1:
            raise ValueError("fuzzy_max_nodes must be >= 1")
        if not 0 < self.fuzzy_decay_lambda < 1:
            raise ValueError("fuzzy_decay_lambda must be in (0, 1)")


# 默认配置实例
DEFAULT_CONFIG = MemoryConfig()
