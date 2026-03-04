"""基础数据类型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class RelationType(Enum):
    """记忆关联类型"""

    RELATED_TO = "related_to"
    CAUSED_BY = "caused_by"
    PART_OF = "part_of"
    CONTRADICTS = "contradicts"
    UPDATES = "updates"


class MemoryCategory(Enum):
    """记忆分类"""

    PREFERENCE = "偏好"
    EVENT = "事件"
    FACT = "事实"
    DECISION = "决策"


@dataclass
class Triple:
    """知识三元组"""

    subject: str
    predicate: str
    object: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Triple":
        return cls(
            subject=data["subject"],
            predicate=data["predicate"],
            object=data["object"],
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class Keywords:
    """关键词结构"""

    primary: list[str] = field(default_factory=list)
    secondary: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    category: str = "事实"

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "entities": self.entities,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Keywords":
        return cls(
            primary=data.get("primary", []),
            secondary=data.get("secondary", []),
            entities=data.get("entities", []),
            category=data.get("category", "事实"),
        )

    def all_keywords(self) -> list[str]:
        """获取所有关键词"""
        return self.primary + self.secondary + self.entities


@dataclass
class PreciseMemory:
    """精准记忆 - 工作区中的原始消息"""

    id: str = field(default_factory=lambda: str(uuid4()))
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "token_count": self.token_count,
            "importance": self.importance,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreciseMemory":
        return cls(
            id=data["id"],
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            token_count=data.get("token_count", 0),
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}),
        )

    def to_message(self) -> dict[str, str]:
        """转换为 LLM 消息格式"""
        return {"role": self.role, "content": self.content}


@dataclass
class FuzzyMemory:
    """模糊记忆 - 压缩后的概括"""

    id: str = field(default_factory=lambda: str(uuid4()))
    summary: str = ""
    triples: list[Triple] = field(default_factory=list)
    keywords: Keywords = field(default_factory=Keywords)
    weight: float = 1.0
    importance: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    source_ids: list[str] = field(default_factory=list)
    access_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "triples": [t.to_dict() for t in self.triples],
            "keywords": self.keywords.to_dict(),
            "weight": self.weight,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "source_ids": self.source_ids,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FuzzyMemory":
        return cls(
            id=data["id"],
            summary=data["summary"],
            triples=[Triple.from_dict(t) for t in data.get("triples", [])],
            keywords=Keywords.from_dict(data.get("keywords", {})),
            weight=data.get("weight", 1.0),
            importance=data.get("importance", 0.5),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            last_accessed=datetime.fromisoformat(
                data.get("last_accessed", data["timestamp"])
            ),
            source_ids=data.get("source_ids", []),
            access_count=data.get("access_count", 0),
        )

    def touch(self) -> None:
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class MemoryEdge:
    """记忆间的关联边"""

    id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation: RelationType = RelationType.RELATED_TO
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEdge":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation=RelationType(data["relation"]),
            weight=data.get("weight", 1.0),
        )


@dataclass
class PersonalitySummary:
    """人设摘要"""

    role: str = ""
    expertise: list[str] = field(default_factory=list)
    target_users: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    valuable_memory_types: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "expertise": self.expertise,
            "target_users": self.target_users,
            "constraints": self.constraints,
            "valuable_memory_types": self.valuable_memory_types,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalitySummary":
        return cls(
            role=data.get("role", ""),
            expertise=data.get("expertise", []),
            target_users=data.get("target_users", []),
            constraints=data.get("constraints", []),
            valuable_memory_types=data.get("valuable_memory_types", []),
            summary=data.get("summary", ""),
        )

    def format_for_prompt(self) -> str:
        """格式化为 Prompt 可用的字符串"""
        parts = [f"角色: {self.role}"]
        if self.expertise:
            parts.append(f"擅长: {', '.join(self.expertise)}")
        if self.valuable_memory_types:
            parts.append(f"有价值的信息类型: {', '.join(self.valuable_memory_types)}")
        if self.constraints:
            parts.append(f"约束: {', '.join(self.constraints)}")
        return "\n".join(parts)


@dataclass
class ImportanceResult:
    """重要性判断结果"""

    importance: float = 0.5
    persona_relevance: float = 0.5
    novelty: float = 0.5
    redundancy: float = 0.0
    action: Literal["add", "update", "skip"] = "add"
    reason: str = ""
    update_target: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportanceResult":
        return cls(
            importance=data.get("importance", 0.5),
            persona_relevance=data.get("persona_relevance", 0.5),
            novelty=data.get("novelty", 0.5),
            redundancy=data.get("redundancy", 0.0),
            action=data.get("action", "add"),
            reason=data.get("reason", ""),
            update_target=data.get("update_target"),
        )


@dataclass
class ValidationResult:
    """校验结果"""

    valid: bool = True
    issues: list[str] = field(default_factory=list)
    should_reject: bool = False
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        return cls(
            valid=data.get("valid", True),
            issues=data.get("issues", []),
            should_reject=data.get("should_reject", False),
            reason=data.get("reason", ""),
        )


@dataclass
class QueryAnalysis:
    """查询分析结果"""

    need_memory: bool = False
    reason: str = ""
    memory_types: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    related_keywords: list[str] = field(default_factory=list)
    time_range: dict[str, Any] | None = None
    confidence: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryAnalysis":
        return cls(
            need_memory=data.get("need_memory", False),
            reason=data.get("reason", ""),
            memory_types=data.get("memory_types", []),
            keywords=data.get("keywords", []),
            related_keywords=data.get("related_keywords", []),
            time_range=data.get("time_range"),
            confidence=data.get("confidence", 0.5),
        )


@dataclass
class DiagnosisResult:
    """诊断结果"""

    relevant: list[dict[str, Any]] = field(default_factory=list)
    need_precise: list[str] = field(default_factory=list)
    need_precise_reason: str = ""
    possibly_missing: list[str] = field(default_factory=list)
    confidence: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiagnosisResult":
        return cls(
            relevant=data.get("relevant", []),
            need_precise=data.get("need_precise", []),
            need_precise_reason=data.get("need_precise_reason", ""),
            possibly_missing=data.get("possibly_missing", []),
            confidence=data.get("confidence", 0.5),
        )

    def get_relevant_ids(self) -> list[str]:
        """获取相关记忆 ID 列表"""
        return [r["id"] for r in self.relevant]


@dataclass
class RetrievalResult:
    """检索结果"""

    fuzzy_memories: list[FuzzyMemory] = field(default_factory=list)
    precise_memories: list[PreciseMemory] = field(default_factory=list)
    confidence: float = 0.5
    reason: str = ""

    def is_empty(self) -> bool:
        return len(self.fuzzy_memories) == 0 and len(self.precise_memories) == 0

    def get_summaries(self) -> list[str]:
        """获取所有模糊记忆的摘要"""
        return [m.summary for m in self.fuzzy_memories]


@dataclass
class CompressionResult:
    """压缩结果"""

    summary: str = ""
    triples: list[Triple] = field(default_factory=list)
    keywords: Keywords = field(default_factory=Keywords)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompressionResult":
        return cls(
            summary=data.get("summary", ""),
            triples=[Triple.from_dict(t) for t in data.get("triples", [])],
            keywords=Keywords.from_dict(data.get("keywords", {})),
        )


@dataclass
class ConflictResult:
    """冲突检测结果"""

    conflict_type: Literal["contradiction", "update", "supplement", "none"] = "none"
    resolution: Literal["override", "merge", "keep_both", "reject"] = "keep_both"
    merged_summary: str = ""
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConflictResult":
        return cls(
            conflict_type=data.get("conflict_type", "none"),
            resolution=data.get("resolution", "keep_both"),
            merged_summary=data.get("merged_summary", ""),
            reason=data.get("reason", ""),
        )
