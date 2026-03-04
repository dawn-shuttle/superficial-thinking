"""持久化存储"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..core.config import MemoryConfig
from ..core.types import FuzzyMemory, MemoryEdge, PreciseMemory


class PersistentStorage:
    """持久存储 - SQLite 数据库"""

    def __init__(self, config: MemoryConfig):
        self._config = config
        self._path = Path(config.db_path)
        self._conn: sqlite3.Connection
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库连接和表"""
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """创建数据库表"""
        schema_sql = (Path(__file__).parent / "schema.sql").read_text()
        self._conn.executescript(schema_sql)
        self._conn.commit()

    def close(self) -> None:
        """关闭数据库连接"""
        self._conn.close()

    # === 精准记忆 ===

    def save_message(self, memory: PreciseMemory) -> None:
        """保存精准记忆"""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO precise_memories
            (id, role, content, timestamp, token_count, importance, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.id,
                memory.role,
                memory.content,
                memory.timestamp.isoformat(),
                memory.token_count,
                memory.importance,
                json.dumps(memory.metadata),
            ),
        )
        self._conn.commit()

    def save_messages(self, memories: list[PreciseMemory]) -> None:
        """批量保存精准记忆"""
        cursor = self._conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO precise_memories
            (id, role, content, timestamp, token_count, importance, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m.id,
                    m.role,
                    m.content,
                    m.timestamp.isoformat(),
                    m.token_count,
                    m.importance,
                    json.dumps(m.metadata),
                )
                for m in memories
            ],
        )
        self._conn.commit()

    def load_message(self, id_: str) -> PreciseMemory | None:
        """加载单条精准记忆"""
        row = self._conn.execute(
            "SELECT * FROM precise_memories WHERE id = ?", (id_,)
        ).fetchone()
        if row:
            return self._row_to_precise(row)
        return None

    def load_messages(self, ids: list[str]) -> list[PreciseMemory]:
        """加载指定精准记忆"""
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT * FROM precise_memories WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_precise(row) for row in rows]

    def load_all_messages(self) -> list[PreciseMemory]:
        """加载所有精准记忆"""
        rows = self._conn.execute(
            "SELECT * FROM precise_memories ORDER BY timestamp"
        ).fetchall()
        return [self._row_to_precise(row) for row in rows]

    def delete_message(self, id_: str) -> None:
        """删除精准记忆"""
        self._conn.execute("DELETE FROM precise_memories WHERE id = ?", (id_,))
        self._conn.commit()

    # === 模糊记忆 ===

    def save_fuzzy(self, memory: FuzzyMemory) -> None:
        """保存模糊记忆"""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO fuzzy_memories
            (id, summary, triples, keywords, weight, importance,
             timestamp, last_accessed, source_ids, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.id,
                memory.summary,
                json.dumps([t.to_dict() for t in memory.triples]),
                json.dumps(memory.keywords.to_dict()),
                memory.weight,
                memory.importance,
                memory.timestamp.isoformat(),
                memory.last_accessed.isoformat(),
                json.dumps(memory.source_ids),
                memory.access_count,
            ),
        )
        self._conn.commit()

    def save_fuzzies(self, memories: list[FuzzyMemory]) -> None:
        """批量保存模糊记忆"""
        cursor = self._conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO fuzzy_memories
            (id, summary, triples, keywords, weight, importance,
             timestamp, last_accessed, source_ids, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m.id,
                    m.summary,
                    json.dumps([t.to_dict() for t in m.triples]),
                    json.dumps(m.keywords.to_dict()),
                    m.weight,
                    m.importance,
                    m.timestamp.isoformat(),
                    m.last_accessed.isoformat(),
                    json.dumps(m.source_ids),
                    m.access_count,
                )
                for m in memories
            ],
        )
        self._conn.commit()

    def load_fuzzy(self, id_: str) -> FuzzyMemory | None:
        """加载单条模糊记忆"""
        row = self._conn.execute(
            "SELECT * FROM fuzzy_memories WHERE id = ?", (id_,)
        ).fetchone()
        if row:
            return self._row_to_fuzzy(row)
        return None

    def load_all_fuzzy(self) -> list[FuzzyMemory]:
        """加载所有模糊记忆"""
        rows = self._conn.execute(
            "SELECT * FROM fuzzy_memories ORDER BY weight DESC"
        ).fetchall()
        return [self._row_to_fuzzy(row) for row in rows]

    def update_fuzzy_access(
        self, id_: str, last_accessed: str, access_count: int, weight: float
    ) -> None:
        """更新模糊记忆的访问信息"""
        self._conn.execute(
            """
            UPDATE fuzzy_memories
            SET last_accessed = ?, access_count = ?, weight = ?
            WHERE id = ?
            """,
            (last_accessed, access_count, weight, id_),
        )
        self._conn.commit()

    def delete_fuzzy(self, id_: str) -> None:
        """删除模糊记忆"""
        self._conn.execute("DELETE FROM fuzzy_memories WHERE id = ?", (id_,))
        # 同时删除相关边
        self._conn.execute(
            "DELETE FROM memory_edges WHERE source_id = ? OR target_id = ?",
            (id_, id_),
        )
        self._conn.commit()

    # === 关联边 ===

    def save_edge(self, edge: MemoryEdge) -> None:
        """保存关联边"""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO memory_edges
            (id, source_id, target_id, relation, weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                edge.id,
                edge.source_id,
                edge.target_id,
                edge.relation.value,
                edge.weight,
            ),
        )
        self._conn.commit()

    def save_edges(self, edges: list[MemoryEdge]) -> None:
        """批量保存关联边"""
        cursor = self._conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO memory_edges
            (id, source_id, target_id, relation, weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (e.id, e.source_id, e.target_id, e.relation.value, e.weight)
                for e in edges
            ],
        )
        self._conn.commit()

    def load_edges_for_source(self, source_id: str) -> list[MemoryEdge]:
        """加载指定源的所有边"""
        rows = self._conn.execute(
            "SELECT * FROM memory_edges WHERE source_id = ?", (source_id,)
        ).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def load_all_edges(self) -> list[MemoryEdge]:
        """加载所有关联边"""
        rows = self._conn.execute("SELECT * FROM memory_edges").fetchall()
        return [self._row_to_edge(row) for row in rows]

    def delete_edges_for_node(self, node_id: str) -> None:
        """删除与指定节点相关的所有边"""
        self._conn.execute(
            "DELETE FROM memory_edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )
        self._conn.commit()

    # === 统计 ===

    def count_precise(self) -> int:
        """统计精准记忆数量"""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM precise_memories"
        ).fetchone()
        return row["cnt"] if row else 0

    def count_fuzzy(self) -> int:
        """统计模糊记忆数量"""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM fuzzy_memories"
        ).fetchone()
        return row["cnt"] if row else 0

    # === 辅助方法 ===

    def _row_to_precise(self, row: sqlite3.Row) -> PreciseMemory:
        return PreciseMemory(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            timestamp=self._parse_datetime(row["timestamp"]),
            token_count=row["token_count"] or 0,
            importance=row["importance"] or 0.5,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_fuzzy(self, row: sqlite3.Row) -> FuzzyMemory:
        from ..core.types import Keywords, Triple

        triples_data = json.loads(row["triples"]) if row["triples"] else []
        keywords_data = json.loads(row["keywords"]) if row["keywords"] else {}
        source_ids = json.loads(row["source_ids"]) if row["source_ids"] else []

        return FuzzyMemory(
            id=row["id"],
            summary=row["summary"],
            triples=[Triple.from_dict(t) for t in triples_data],
            keywords=Keywords.from_dict(keywords_data),
            weight=row["weight"] or 1.0,
            importance=row["importance"] or 0.5,
            timestamp=self._parse_datetime(row["timestamp"]),
            last_accessed=self._parse_datetime(
                row["last_accessed"] or row["timestamp"]
            ),
            source_ids=source_ids,
            access_count=row["access_count"] or 0,
        )

    def _row_to_edge(self, row: sqlite3.Row) -> MemoryEdge:
        from ..core.types import RelationType

        return MemoryEdge(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=RelationType(row["relation"]),
            weight=row["weight"] or 1.0,
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> Any:
        from datetime import datetime

        if not value:
            return datetime.now()
        return datetime.fromisoformat(value)

    # === 事务 ===

    def begin_transaction(self) -> None:
        """开始事务"""
        self._conn.execute("BEGIN")

    def commit(self) -> None:
        """提交事务"""
        self._conn.commit()

    def rollback(self) -> None:
        """回滚事务"""
        self._conn.rollback()
