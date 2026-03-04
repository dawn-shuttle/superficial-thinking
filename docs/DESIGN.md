# Superficial-Thinking 设计文档

> 基于推理的 LLM 记忆层

## 目录

- [一、概述](#一概述)
- [二、整体架构](#二整体架构)
- [三、数据结构](#三数据结构)
- [四、三层存储](#四三层存储)
- [五、记忆智能体](#五记忆智能体)
- [六、核心流程](#六核心流程)
- [七、Prompt 设计](#七prompt-设计)
- [八、与 intelligence 集成](#八与-intelligence-集成)
- [九、模块结构](#九模块结构)
- [十、配置项](#十配置项)
- [十一、使用示例](#十一使用示例)
- [十二、错误处理与边界情况](#十二错误处理与边界情况)
- [十三、记忆冲突与更新](#十三记忆冲突与更新)
- [十四、模糊记忆淘汰策略](#十四模糊记忆淘汰策略)
- [十五、性能优化](#十五性能优化)
- [十六、异步架构](#十六异步架构)
- [十七、生命周期管理](#十七生命周期管理)
- [十八、测试策略](#十八测试策略)
- [十九、扩展点设计](#十九扩展点设计)
- [附录](#附录)

---

## 一、概述

### 1.1 项目定位

`superficial-thinking` 是一个基于推理的 LLM 记忆层，核心思想：

> 记忆不是存储的原样重现，而是通过推理重建的产物。

### 1.2 核心特性

- **智能体管理**：由专门的记忆智能体负责记忆的分类、评估和维护
- **三层结构**：工作记忆（精准）→ 模糊记忆（概括）→ 持久存储（完整）
- **图结构关联**：记忆之间通过图结构建立关联，支持关系遍历
- **人设感知**：记忆重要性评估基于 LLM 人设，而非孤立判断
- **按需加载**：模糊记忆可触发精准记忆的动态加载

### 1.3 设计原则

1. **无外部依赖**：仅使用 Python 标准库 + `dawn_shuttle_intelligence`
2. **单对话模型**：专注于单次对话，无需用户分区或多租户
3. **推理驱动**：关键决策由 LLM 判断，而非硬编码规则

---

## 二、整体架构

```
┌────────────────────────────────────────────────────────────────┐
│                      主对话 LLM                                  │
│                  (通过 intelligence 调用)                        │
└───────────────────────────┬────────────────────────────────────┘
                            │ 调用记忆工具
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                  MemoryManager (记忆管理器)                      │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              MemoryAgent (记忆智能体)                      │  │
│  │         使用 intelligence 接收 LLM 实例                    │  │
│  │                                                           │  │
│  │   • extract(): 提取中心点/三元组                           │  │
│  │   • judge_importance(): 判断重要性（基于人设）             │  │
│  │   • validate(): 校验正确性                                 │  │
│  │   • compress(): 压缩精准记忆为模糊记忆                     │  │
│  │   • relate(): 建立记忆间关联                               │  │
│  │   • analyze_query(): 分析查询意图                          │  │
│  │   • diagnose(): 诊断候选记忆                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│        ┌───────────────────┼───────────────────┐               │
│        ▼                   ▼                   ▼               │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐         │
│  │WorkingMem│        │FuzzyMem  │        │ Storage  │         │
│  │ 工作记忆  │        │ 模糊记忆  │        │ 持久存储  │         │
│  │ (精准)   │        │ (概括)   │        │ (完整)   │         │
│  └──────────┘        └──────────┘        └──────────┘         │
│        │                   │                   │               │
│        │    内存           │    内存           │    磁盘        │
│        ▼                   ▼                   ▼               │
│   MessageQueue         MemoryGraph          SQLite            │
│                                            KeywordIndex        │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 组件职责

| 组件 | 职责 | 存储位置 |
|-----|------|---------|
| MemoryManager | 统一入口，协调各组件 | - |
| MemoryAgent | 智能体，负责 LLM 推理判断 | - |
| WorkingMemory | 最近对话的精准记忆 | 内存 |
| FuzzyMemoryGraph | 历史对话的模糊记忆图 | 内存 |
| PersistentStorage | 完整历史数据持久化 | 磁盘 (SQLite) |
| KeywordIndex | 关键词倒排索引 | 内存 |

---

## 三、数据结构

### 3.1 精准记忆 (PreciseMemory)

工作区中的原始消息，保持完整内容。

```python
@dataclass
class PreciseMemory:
    """精准记忆 - 工作区中的原始消息"""
    id: str                    # UUID
    role: Literal["user", "assistant", "system"]
    content: str               # 原始文本
    timestamp: datetime        # 时间戳
    token_count: int           # token 数量
    importance: float          # 重要性分数 [0, 1]
    metadata: dict             # 扩展元数据
```

### 3.2 模糊记忆 (FuzzyMemory)

压缩后的概括，存储核心信息和关联。

```python
@dataclass
class FuzzyMemory:
    """模糊记忆 - 压缩后的概括"""
    id: str                    # UUID
    summary: str               # 概括摘要
    triples: list[Triple]      # 三元组列表
    keywords: Keywords         # 关键词
    weight: float              # 权重 [0, 1]，随时间衰减
    importance: float          # 原始重要性分数
    timestamp: datetime        # 创建时间
    last_accessed: datetime    # 最后访问时间
    source_ids: list[str]      # 来源精准记忆ID (指向持久化)
    access_count: int          # 访问次数
```

### 3.3 三元组 (Triple)

知识的最小单元，用于结构化表示。

```python
@dataclass
class Triple:
    """知识三元组"""
    subject: str               # 主语
    predicate: str             # 谓语
    object: str                # 宾语
    confidence: float          # 置信度 [0, 1]
```

**示例**：
```
("用户", "偏好", "Python编程")
("用户", "正在开发", "数据分析项目")
("用户", "使用框架", "Pandas")
```

### 3.4 关键词 (Keywords)

用于检索的分类和索引信息。

```python
@dataclass
class Keywords:
    """关键词结构"""
    primary: list[str]         # 核心关键词 (3-5个)
    secondary: list[str]       # 扩展关键词
    entities: list[str]        # 命名实体
    category: str              # 分类: 偏好|事件|事实|决策
```

**分类说明**：

| 分类 | 说明 | 示例 |
|-----|------|-----|
| 偏好 | 用户喜好、习惯 | "喜欢用 Python" |
| 事件 | 具体发生的事情 | "昨天完成了一个项目" |
| 事实 | 客观信息 | "用户是后端开发者" |
| 决策 | 用户做出的选择 | "决定使用 FastAPI" |

### 3.5 记忆关联 (MemoryEdge)

模糊记忆之间的关系。

```python
@dataclass
class MemoryEdge:
    """记忆间的关联边"""
    source_id: str             # 源记忆ID
    target_id: str             # 目标记忆ID
    relation: RelationType     # 关联类型
    weight: float              # 关联强度 [0, 1]

class RelationType(Enum):
    """关联类型"""
    RELATED_TO = "related_to"      # 一般相关
    CAUSED_BY = "caused_by"        # 因果关系
    PART_OF = "part_of"            # 包含关系
    CONTRADICTS = "contradicts"    # 矛盾关系
    UPDATES = "updates"            # 更新关系
```

### 3.6 检索结果 (RetrievalResult)

```python
@dataclass
class RetrievalResult:
    """检索结果"""
    fuzzy_memories: list[FuzzyMemory]   # 相关模糊记忆
    precise_memories: list[PreciseMemory]  # 加载的精准记忆
    confidence: float                   # 检索置信度
    reason: str                         # 检索理由
```

---

## 四、三层存储

### 4.1 设计理念

```
┌─────────────────────────────────────┐
│         工作记忆（精准）              │
│   最近 N 条消息原文                  │
│   内存队列，FIFO 淘汰                │
└──────────────┬──────────────────────┘
               │ 超出容量时压缩
               ▼
┌─────────────────────────────────────┐
│         模糊记忆（概括）              │
│   历史消息的摘要/三元组               │
│   内存图结构，带权重衰减              │
└──────────────┬──────────────────────┘
               │ 提及时加载
               ▼
┌─────────────────────────────────────┐
│         持久存储（完整）              │
│   所有原始消息                       │
│   SQLite，可恢复                     │
└─────────────────────────────────────┘
```

### 4.2 工作记忆 (WorkingMemory)

**职责**：保持最近对话的精准上下文

```python
class WorkingMemory:
    """工作记忆 - 内存中的消息队列"""
    
    def __init__(
        self,
        max_messages: int = 20,
        max_tokens: int = 4000
    ):
        self._queue: deque[PreciseMemory] = deque()
        self._max_messages = max_messages
        self._max_tokens = max_tokens
        self._current_tokens = 0
    
    def add(self, memory: PreciseMemory) -> PreciseMemory | None:
        """
        添加记忆，返回被淘汰的记忆（如有）
        
        淘汰条件：
        1. 消息数量超过 max_messages
        2. 总 token 数超过 max_tokens
        """
        ...
    
    def get_context(self) -> list[dict]:
        """获取用于 LLM 的上下文格式"""
        return [
            {"role": m.role, "content": m.content}
            for m in self._queue
        ]
    
    def is_full(self) -> bool:
        """检查是否达到容量上限"""
        return (
            len(self._queue) >= self._max_messages or
            self._current_tokens >= self._max_tokens
        )
    
    def clear(self) -> list[PreciseMemory]:
        """清空并返回所有记忆"""
        ...
```

### 4.3 模糊记忆图 (FuzzyMemoryGraph)

**职责**：存储压缩后的概括，维护图结构关联

```python
class FuzzyMemoryGraph:
    """模糊记忆图 - 内存中的图结构"""
    
    def __init__(self, max_nodes: int = 100):
        self._nodes: dict[str, FuzzyMemory] = {}
        self._edges: dict[str, list[MemoryEdge]] = {}  # 邻接表
        self._max_nodes = max_nodes
    
    def add(self, memory: FuzzyMemory) -> FuzzyMemory | None:
        """添加模糊记忆节点，返回被淘汰的节点（如有）"""
        ...
    
    def relate(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0
    ) -> None:
        """建立关联边"""
        ...
    
    def decay_weights(self, lambda_: float = 0.01) -> None:
        """
        权重衰减
        
        公式: w(t) = w₀ × exp(-λ × Δt)
        - λ: 衰减率
        - Δt: 距离上次访问的时间间隔
        """
        now = datetime.now()
        for node in self._nodes.values():
            delta_hours = (now - node.last_accessed).total_seconds() / 3600
            node.weight *= math.exp(-lambda_ * delta_hours)
    
    def get_summaries(self) -> list[str]:
        """获取所有记忆摘要（用于检索和评估）"""
        return [m.summary for m in self._nodes.values()]
    
    def get_neighbors(
        self,
        memory_id: str,
        depth: int = 2,
        relation_types: list[RelationType] | None = None
    ) -> list[FuzzyMemory]:
        """
        获取关联记忆（BFS 遍历）
        
        Args:
            memory_id: 起始记忆ID
            depth: 遍历深度
            relation_types: 只跟随指定类型的边
        """
        ...
    
    def search_by_keywords(
        self,
        keywords: list[str],
        top_k: int = 10
    ) -> list[FuzzyMemory]:
        """通过关键词搜索"""
        results = []
        for node in self._nodes.values():
            score = self._calculate_keyword_score(node, keywords)
            if score > 0:
                results.append((node, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results[:top_k]]
```

**权重衰减公式**：

```
w(t) = w₀ × exp(-λ × Δt)

其中：
- w₀: 初始权重（等于重要性分数）
- λ: 衰减率，默认 0.01
- Δt: 距离上次访问的时间（小时）
```

### 4.4 持久存储 (PersistentStorage)

**职责**：完整保存所有原始数据，支持恢复

```python
class PersistentStorage:
    """持久存储 - SQLite 数据库"""
    
    def __init__(self, db_path: str = "memory.db"):
        self._path = db_path
        self._conn = sqlite3.connect(db_path)
        self._init_tables()
    
    def save_message(self, memory: PreciseMemory) -> None:
        """保存精准记忆"""
        ...
    
    def save_fuzzy(self, memory: FuzzyMemory) -> None:
        """保存模糊记忆"""
        ...
    
    def save_edge(self, edge: MemoryEdge) -> None:
        """保存关联边"""
        ...
    
    def load_messages(self, ids: list[str]) -> list[PreciseMemory]:
        """加载指定精准记忆"""
        ...
    
    def load_all_fuzzy(self) -> list[FuzzyMemory]:
        """加载所有模糊记忆（启动时恢复）"""
        ...
    
    def load_all_edges(self) -> list[MemoryEdge]:
        """加载所有关联边"""
        ...
```

**数据库 Schema**：

```sql
-- 精准记忆表
CREATE TABLE IF NOT EXISTS precise_memories (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    token_count INTEGER,
    importance REAL,
    metadata TEXT
);

CREATE INDEX idx_precise_timestamp ON precise_memories(timestamp);

-- 模糊记忆表
CREATE TABLE IF NOT EXISTS fuzzy_memories (
    id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    triples TEXT,
    keywords TEXT,
    weight REAL,
    importance REAL,
    timestamp TEXT,
    last_accessed TEXT,
    source_ids TEXT,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX idx_fuzzy_weight ON fuzzy_memories(weight);
CREATE INDEX idx_fuzzy_timestamp ON fuzzy_memories(timestamp);

-- 记忆关联表
CREATE TABLE IF NOT EXISTS memory_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL,
    FOREIGN KEY (source_id) REFERENCES fuzzy_memories(id),
    FOREIGN KEY (target_id) REFERENCES fuzzy_memories(id)
);

CREATE INDEX idx_edge_source ON memory_edges(source_id);
CREATE INDEX idx_edge_target ON memory_edges(target_id);
```

### 4.5 关键词索引 (KeywordIndex)

**职责**：支持高效关键词检索

```python
class KeywordIndex:
    """关键词倒排索引"""
    
    def __init__(self):
        # 关键词 → 记忆ID集合
        self._index: dict[str, set[str]] = {}
        # 分类 → 记忆ID集合
        self._category_index: dict[str, set[str]] = {}
    
    def add(self, memory_id: str, keywords: Keywords) -> None:
        """添加记忆到索引"""
        # 索引所有关键词
        all_keywords = (
            keywords.primary + 
            keywords.secondary + 
            keywords.entities
        )
        for kw in all_keywords:
            if kw not in self._index:
                self._index[kw] = set()
            self._index[kw].add(memory_id)
        
        # 索引分类
        if keywords.category not in self._category_index:
            self._category_index[keywords.category] = set()
        self._category_index[keywords.category].add(memory_id)
    
    def search(
        self,
        keywords: list[str],
        categories: list[str] | None = None
    ) -> list[str]:
        """
        搜索包含任一关键词的记忆ID
        
        Args:
            keywords: 关键词列表
            categories: 可选的分类过滤
        """
        result = set()
        for kw in keywords:
            if kw in self._index:
                result.update(self._index[kw])
        
        if categories:
            category_set = set()
            for cat in categories:
                if cat in self._category_index:
                    category_set.update(self._category_index[cat])
            result &= category_set
        
        return list(result)
    
    def remove(self, memory_id: str, keywords: Keywords) -> None:
        """从索引中移除记忆"""
        all_keywords = (
            keywords.primary + 
            keywords.secondary + 
            keywords.entities
        )
        for kw in all_keywords:
            if kw in self._index:
                self._index[kw].discard(memory_id)
        
        if keywords.category in self._category_index:
            self._category_index[keywords.category].discard(memory_id)
```

---

## 五、记忆智能体

### 5.1 核心职责

记忆智能体 (`MemoryAgent`) 是整个系统的"大脑"，负责所有需要 LLM 推理的决策。

| 方法 | 职责 |
|-----|------|
| `extract_personality()` | 从 system_prompt 提取人设摘要 |
| `validate()` | 校验记忆是否与人设冲突 |
| `judge_importance()` | 评估记忆重要性 |
| `extract_keywords()` | 提取关键词和分类 |
| `compress()` | 压缩精准记忆为模糊记忆 |
| `relate()` | 判断记忆间关联 |
| `analyze_query()` | 分析查询意图 |
| `diagnose()` | 诊断候选记忆 |

### 5.2 类定义

```python
from dawn_shuttle_intelligence import LLM

class MemoryAgent:
    """记忆管理智能体"""
    
    def __init__(self, llm: LLM, system_prompt: str):
        """
        Args:
            llm: LLM 实例（来自 intelligence）
            system_prompt: 主对话的人设/角色设定
        """
        self._llm = llm
        self._system_prompt = system_prompt
        self._personality: PersonalitySummary | None = None
    
    @property
    def personality(self) -> PersonalitySummary:
        """获取人设摘要（懒加载）"""
        if self._personality is None:
            self._personality = self._extract_personality()
        return self._personality
    
    async def _extract_personality(self) -> PersonalitySummary:
        """从 system_prompt 提取人设摘要"""
        ...
```

### 5.3 人设摘要

```python
@dataclass
class PersonalitySummary:
    """人设摘要"""
    role: str                      # 角色身份
    expertise: list[str]           # 擅长领域
    target_users: list[str]        # 服务对象
    constraints: list[str]         # 行为约束
    valuable_memory_types: list[str]  # 有价值的记忆类型
    summary: str                   # 一句话概括
```

---

## 六、核心流程

### 6.1 添加记忆流程

```
新消息到达
    │
    ▼
┌─────────────────────┐
│   创建精准记忆       │
│   (PreciseMemory)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   校验正确性         │
│   (validate)        │
│   检查是否与人设冲突  │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │ 冲突?     │
     ▼           ▼
   是          否
     │           │
     ▼           ▼
┌─────────┐  ┌─────────────────────┐
│ 拒绝/标记│  │   评估重要性         │
└─────────┘  │   (judge_importance) │
             │   基于人设+已有记忆   │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │   添加到工作记忆     │
             │   (WorkingMemory)   │
             └──────────┬──────────┘
                        │
                  ┌─────┴─────┐
                  │ 容量满?   │
                  ▼           ▼
                是          否
                  │           │
                  ▼           ▼
        ┌─────────────┐  ┌─────────┐
        │ 淘汰最早消息 │  │  结束   │
        └──────┬──────┘  └─────────┘
               │
               ├──────────────────────┐
               ▼                      ▼
        ┌─────────────┐        ┌─────────────┐
        │ 保存到持久化 │        │ 提取关键词   │
        └─────────────┘        └──────┬──────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │ 压缩为模糊   │
                               │ 记忆        │
                               └──────┬──────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │ 建立图关联   │
                               │ (relate)    │
                               └──────┬──────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │ 保存模糊记忆 │
                               │ 更新索引     │
                               └─────────────┘
```

### 6.2 检索记忆流程（三阶段）

```
用户查询到达
    │
    ▼
┌─────────────────────────────────┐
│ 第一阶段：分析查询意图            │
│ (analyze_query)                 │
│                                 │
│ LLM 分析：                       │
│ • 是否需要历史记忆               │
│ • 需要什么类型的记忆             │
│ • 提取主关键词和扩展关键词        │
└────────────────┬────────────────┘
                 │
           ┌─────┴─────┐
           │ 需要记忆? │
           ▼           ▼
          否          是
           │           │
           ▼           ▼
       ┌────────┐  ┌─────────────────────────────────┐
       │ 返回空 │  │ 第二阶段：检索候选记忆            │
       └────────┘  │                                 │
                   │ 1. 主关键词精确匹配               │
                   │ 2. 扩展关键词模糊匹配             │
                   │ 3. 分类过滤                      │
                   │ 4. 按权重排序，取 top_k          │
                   └────────────────┬────────────────┘
                                    │
                                    ▼
                   ┌─────────────────────────────────┐
                   │ 第三阶段：LLM 诊断筛选            │
                   │ (diagnose)                      │
                   │                                 │
                   │ LLM 判断：                       │
                   │ • 哪些真正相关                   │
                   │ • 哪些需要加载精准版本           │
                   │ • 是否有遗漏                    │
                   └────────────────┬────────────────┘
                                    │
                                    ▼
                   ┌─────────────────────────────────┐
                   │ 加载精准记忆（如需要）            │
                   │ 从 PersistentStorage 加载       │
                   └────────────────┬────────────────┘
                                    │
                                    ▼
                   ┌─────────────────────────────────┐
                   │ 返回 RetrievalResult             │
                   └─────────────────────────────────┘
```

### 6.3 压缩流程

```python
async def compress(
    self,
    memories: list[PreciseMemory]
) -> FuzzyMemory:
    """
    将多条精准记忆压缩为一条模糊记忆
    
    步骤：
    1. 提取中心点摘要
    2. 抽取三元组
    3. 提取关键词
    4. 计算平均重要性
    5. 创建模糊记忆对象
    """
    ...
```

---

## 七、Prompt 设计

### 7.1 人设提取

```python
EXTRACT_PERSONALITY_PROMPT = """
从以下 LLM 人设/系统提示词中提取核心要点。

【人设内容】
{system_prompt}

【提取要点】
1. 角色身份：这个 LLM 是谁？
2. 核心能力：擅长什么领域？
3. 服务对象：为谁提供服务？
4. 行为约束：有什么限制或规则？
5. 需要记住的信息类型：什么信息对人设有价值？

【输出格式】
{{
    "role": "角色身份",
    "expertise": ["擅长领域1", "擅长领域2"],
    "target_users": ["服务对象1", "服务对象2"],
    "constraints": ["约束1", "约束2"],
    "valuable_memory_types": ["偏好", "背景", "目标"],
    "summary": "一句话概括"
}}
"""
```

### 7.2 记忆校验

```python
VALIDATE_MEMORY_PROMPT = """
校验记忆内容是否与 LLM 人设约束一致。

【LLM 人设】
{personality_summary}

【待校验记忆】
角色: {role}
内容: {content}

【校验项】
1. 是否违反人设的道德/安全约束？
2. 是否与人设的知识边界矛盾？
3. 是否试图改变人设的核心行为？

【输出格式】
{{
    "valid": true/false,
    "issues": ["问题1", "问题2"],
    "should_reject": true/false,
    "reason": "拒绝原因（如适用）"
}}
"""
```

### 7.3 重要性判断

```python
JUDGE_IMPORTANCE_PROMPT = """
你是一个记忆评估专家。根据 LLM 人设和已有记忆，判断新记忆的重要性。

【LLM 人设核心要点】
角色: {role}
擅长: {expertise}
有价值的信息类型: {valuable_memory_types}

【已有记忆摘要】
{existing_summaries}

【新记忆内容】
角色: {new_role}
内容: {new_content}

【评估维度】
1. 人设相关性：这条记忆对履行人设职责有帮助吗？（0-1）
2. 新颖性：是否是人设需要但尚未记录的信息？（0-1）
3. 正确性：是否与已有记忆或人设约束冲突？
4. 冗余性：是否可由已有记忆推断？（0-1）

【输出格式】
{{
    "importance": 0.0-1.0,
    "persona_relevance": 0.0-1.0,
    "novelty": 0.0-1.0,
    "redundancy": 0.0-1.0,
    "action": "add|update|skip",
    "reason": "判断理由",
    "update_target": "如果需要更新，指明更新哪条记忆的ID"
}}
"""
```

### 7.4 关键词提取

```python
EXTRACT_KEYWORDS_PROMPT = """
从以下记忆内容中提取关键词。

【记忆内容】
{content}

【提取规则】
1. 实体词：人名、地名、物品、技术名词等
2. 属性词：偏好、状态、特征等
3. 动作词：行为、事件等
4. 时间词：具体时间或时间范围

【输出格式】
{{
    "primary_keywords": ["核心关键词1", "核心关键词2", "核心关键词3"],
    "secondary_keywords": ["扩展关键词1", "扩展关键词2"],
    "entities": ["命名实体1", "命名实体2"],
    "category": "偏好|事件|事实|决策"
}}
"""
```

### 7.5 记忆压缩

```python
COMPRESS_MEMORY_PROMPT = """
将以下多条精准记忆压缩为一条模糊记忆。

【人设要点】
{personality_summary}

【精准记忆列表】
{memories}

【压缩任务】
1. 提取共同主题和核心信息
2. 生成一句话概括摘要
3. 抽取知识三元组（主语，谓语，宾语）
4. 提取关键词

【输出格式】
{{
    "summary": "一句话概括",
    "triples": [
        {{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9}},
        ...
    ],
    "keywords": {{
        "primary": ["关键词1", "关键词2"],
        "secondary": ["扩展词1"],
        "entities": ["实体1"],
        "category": "分类"
    }}
}}
"""
```

### 7.6 关联判断

```python
RELATE_MEMORY_PROMPT = """
判断新记忆与现有记忆之间的关联关系。

【新记忆】
{new_memory}

【现有记忆列表】
{existing_memories}

【关联类型】
- related_to: 一般相关
- caused_by: 因果关系（新记忆导致旧记忆）
- part_of: 包含关系
- contradicts: 矛盾关系
- updates: 更新关系（新记忆更新旧记忆）

【输出格式】
{{
    "relations": [
        {{
            "target_id": "记忆ID",
            "relation": "关联类型",
            "weight": 0.0-1.0,
            "reason": "判断理由"
        }},
        ...
    ]
}}
"""
```

### 7.7 查询分析

```python
ANALYZE_QUERY_PROMPT = """
分析用户查询，判断需要哪些记忆支持。

【LLM 人设】
{personality_summary}

【用户查询】
{query}

【当前工作记忆】
{working_memory}

【已有的模糊记忆摘要列表】
{fuzzy_summaries}

【分析任务】
1. 判断是否需要检索历史记忆
2. 如果需要，确定需要什么类型的记忆
3. 提取主关键词和扩展关键词

【输出格式】
{{
    "need_memory": true/false,
    "reason": "为什么需要/不需要",
    "memory_types": ["偏好", "事件", "事实", "决策"],
    "keywords": ["主关键词1", "主关键词2"],
    "related_keywords": ["扩展词1", "扩展词2"],
    "time_range": {{"start": "...", "end": "..."}} | null,
    "confidence": 0.0-1.0
}}
"""
```

### 7.8 记忆诊断

```python
DIAGNOSE_MEMORY_PROMPT = """
对候选记忆进行诊断，确保不遗漏或误解。

【用户原始查询】
{query}

【候选记忆列表】
{candidate_memories}

【诊断任务】
1. 判断每条记忆是否真正相关
2. 判断是否需要加载精准记忆（模糊版本不够清晰时）
3. 检查是否有遗漏的重要记忆类型

【输出格式】
{{
    "relevant": [
        {{
            "id": "记忆ID",
            "relevance": 0.0-1.0,
            "reason": "相关性理由"
        }}
    ],
    "need_precise": ["需要加载精准版本的ID"],
    "need_precise_reason": "为什么需要精准版本",
    "possibly_missing": ["可能遗漏的记忆类型"],
    "confidence": 0.0-1.0
}}
"""
```

---

## 八、与 intelligence 集成

### 8.1 集成方式

`superficial-thinking` 作为 `intelligence` 的下游依赖：

```python
from dawn_shuttle_intelligence import LLM
from dawn_shuttle_superficial_thinking import MemoryManager

# 1. 创建 LLM 实例（使用 intelligence）
llm = LLM(provider="openai", model="gpt-4")

# 2. 创建记忆管理器，注入 LLM 和人设
memory = MemoryManager(
    llm=llm,
    system_prompt="你是一个编程助手..."
)

# 3. 在对话中使用
await memory.add_message(role="user", content="...")
context = memory.get_context()
```

### 8.2 MemoryManager 完整接口

```python
class MemoryManager:
    """记忆管理器 - 统一入口"""
    
    def __init__(
        self,
        llm: LLM,
        system_prompt: str,
        config: MemoryConfig | None = None
    ):
        """
        Args:
            llm: intelligence 的 LLM 实例
            system_prompt: 主对话的人设
            config: 配置项
        """
        ...
    
    # === 写入操作 ===
    
    async def add_message(
        self,
        role: str,
        content: str,
        metadata: dict | None = None
    ) -> None:
        """添加消息到记忆系统"""
        ...
    
    async def add_messages(
        self,
        messages: list[dict]
    ) -> None:
        """批量添加消息"""
        ...
    
    # === 读取操作 ===
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5
    ) -> RetrievalResult:
        """检索相关记忆"""
        ...
    
    def get_context(
        self,
        include_fuzzy: bool = True
    ) -> list[dict]:
        """
        获取当前上下文（用于 LLM）
        
        Args:
            include_fuzzy: 是否包含模糊记忆摘要
        """
        ...
    
    # === 状态操作 ===
    
    def get_stats(self) -> dict:
        """获取记忆系统状态"""
        return {
            "working_count": len(self._working),
            "fuzzy_count": len(self._fuzzy),
            "total_tokens": self._working.total_tokens,
        }
    
    async def decay(self) -> None:
        """手动触发权重衰减"""
        self._fuzzy.decay_weights()
    
    def clear_working(self) -> None:
        """清空工作记忆（保留持久化）"""
        self._working.clear()
    
    # === 持久化操作 ===
    
    async def save(self) -> None:
        """保存所有状态到磁盘"""
        ...
    
    async def load(self) -> None:
        """从磁盘恢复状态"""
        ...
```

### 8.3 配置项

```python
@dataclass
class MemoryConfig:
    """记忆系统配置"""
    
    # 工作记忆
    working_max_messages: int = 20
    working_max_tokens: int = 4000
    
    # 模糊记忆
    fuzzy_max_nodes: int = 100
    fuzzy_decay_lambda: float = 0.01
    
    # 人设相关
    personality_update_interval: int = 100  # 每 N 条消息重新提取人设摘要
    
    # 检索
    retrieval_top_k: int = 10
    retrieval_candidates: int = 20
    retrieval_threshold: float = 0.3
    
    # 持久化
    db_path: str = "memory.db"
    auto_save: bool = True
    save_interval: int = 10  # 每 N 条消息自动保存
```

---

## 九、模块结构

```
dawn_shuttle/dawn_shuttle_superficial_thinking/
├── __init__.py              # 导出 MemoryManager
└── src/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── types.py         # 数据类型定义
    │   ├── memory.py        # 记忆单元类
    │   ├── config.py        # 配置项
    │   └── prompts.py       # Prompt 模板
    │
    ├── data/
    │   ├── __init__.py
    │   ├── working.py       # WorkingMemory
    │   ├── fuzzy.py         # FuzzyMemoryGraph
    │   ├── index.py         # KeywordIndex
    │   └── agent.py         # MemoryAgent
    │
    └── db/
        ├── __init__.py
        ├── storage.py       # PersistentStorage
        └── schema.sql       # 数据库建表语句
```

### 9.1 模块职责

| 模块 | 文件 | 职责 |
|-----|------|------|
| core | types.py | 数据类定义：PreciseMemory, FuzzyMemory, Triple 等 |
| core | memory.py | 记忆单元的辅助方法 |
| core | config.py | MemoryConfig 配置类 |
| core | prompts.py | 所有 Prompt 模板常量 |
| data | working.py | WorkingMemory 类 |
| data | fuzzy.py | FuzzyMemoryGraph 类 |
| data | index.py | KeywordIndex 类 |
| data | agent.py | MemoryAgent 类 |
| db | storage.py | PersistentStorage 类 |
| db | schema.sql | SQLite 建表语句 |

---

## 十、配置项

### 10.1 完整配置

```python
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
```

### 10.2 默认配置说明

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| working_max_messages | 20 | 约等于 10 轮对话 |
| working_max_tokens | 4000 | 适合大多数上下文窗口 |
| fuzzy_max_nodes | 100 | 平衡内存占用和覆盖范围 |
| fuzzy_decay_lambda | 0.01 | 半衰期约 69 小时 |
| retrieval_top_k | 10 | 避免上下文过长 |
| retrieval_candidates | 20 | 给 LLM 诊断足够候选 |

---

## 十一、使用示例

### 11.1 基本使用

```python
import asyncio
from dawn_shuttle_intelligence import LLM
from dawn_shuttle_superficial_thinking import MemoryManager

async def main():
    # 创建 LLM 实例
    llm = LLM(provider="openai", model="gpt-4")
    
    # 定义人设
    SYSTEM_PROMPT = """
    你是一个专业的编程助手，帮助用户解决编程问题。
    你擅长 Python、JavaScript、Go 等语言。
    记住用户的编程偏好和项目背景。
    """
    
    # 创建记忆管理器
    memory = MemoryManager(
        llm=llm,
        system_prompt=SYSTEM_PROMPT
    )
    
    # 添加对话
    await memory.add_message("user", "我喜欢用 Python 做数据分析")
    await memory.add_message("assistant", "好的，我记住了。你偏好 Python 进行数据分析工作。")
    await memory.add_message("user", "我正在用 Pandas 处理一个大型 CSV 文件")
    
    # 获取上下文
    context = memory.get_context()
    print(context)
    
    # 检索相关记忆
    result = await memory.retrieve("我的编程偏好是什么？")
    print(result)

asyncio.run(main())
```

### 11.2 与主对话集成

```python
async def chat_with_memory(user_input: str, memory: MemoryManager, llm: LLM):
    # 1. 检索相关记忆
    retrieval = await memory.retrieve(user_input)
    
    # 2. 构建消息
    messages = []
    
    # 添加模糊记忆摘要（如有）
    if retrieval.fuzzy_memories:
        memory_context = "【历史记忆摘要】\n" + "\n".join([
            m.summary for m in retrieval.fuzzy_memories
        ])
        messages.append({"role": "system", "content": memory_context})
    
    # 添加精准记忆（如有加载）
    for pm in retrieval.precise_memories:
        messages.append({"role": pm.role, "content": pm.content})
    
    # 添加工作记忆
    messages.extend(memory.get_context())
    
    # 添加当前用户输入
    messages.append({"role": "user", "content": user_input})
    
    # 3. 调用 LLM
    response = await llm.chat(messages)
    
    # 4. 记录对话
    await memory.add_message("user", user_input)
    await memory.add_message("assistant", response.content)
    
    return response.content
```

### 11.3 手动控制

```python
# 手动触发衰减
await memory.decay()

# 获取统计信息
stats = memory.get_stats()
print(f"工作记忆: {stats['working_count']} 条")
print(f"模糊记忆: {stats['fuzzy_count']} 条")

# 手动保存
await memory.save()

# 清空工作记忆（开始新对话）
memory.clear_working()
```

---

## 十二、错误处理与边界情况

### 12.1 异常类定义

```python
class MemoryError(Exception):
    """记忆系统基础异常"""
    pass

class MemoryValidationError(MemoryError):
    """记忆校验失败"""
    pass

class MemoryConflictError(MemoryError):
    """记忆冲突"""
    pass

class StorageError(MemoryError):
    """存储操作失败"""
    pass

class LLMCallError(MemoryError):
    """LLM 调用失败"""
    pass
```

### 12.2 边界情况处理

| 场景 | 处理方式 |
|-----|---------|
| 冷启动（无历史记忆） | 跳过重要性对比，直接评估新颖性 |
| LLM 调用失败 | 使用降级策略（默认重要性 0.5） |
| 存储写入失败 | 内存数据保留，记录日志，重试 |
| 模糊记忆图满 | 淘汰权重最低的节点 |
| 关键词索引为空 | 返回空结果，不报错 |
| 精准记忆加载失败 | 仅返回模糊版本 |

### 12.3 降级策略

```python
class MemoryAgent:
    
    async def judge_importance(self, ...) -> ImportanceResult:
        try:
            return await self._llm_judge_importance(...)
        except LLMCallError:
            # 降级：使用规则判断
            return self._rule_based_importance(...)
    
    def _rule_based_importance(
        self,
        new_memory: PreciseMemory,
        existing_summaries: list[str]
    ) -> ImportanceResult:
        """规则降级判断"""
        score = 0.5
        
        # 用户消息通常更重要
        if new_memory.role == "user":
            score += 0.1
        
        # 包含关键词提示重要性
        important_keywords = ["偏好", "喜欢", "决定", "重要", "记住"]
        for kw in important_keywords:
            if kw in new_memory.content:
                score += 0.1
                break
        
        return ImportanceResult(
            importance=min(score, 1.0),
            action="add",
            reason="降级规则判断"
        )
```

---

## 十三、记忆冲突与更新

### 13.1 冲突检测

当新记忆与已有记忆矛盾时的处理流程：

```
新记忆到达
    │
    ▼
┌─────────────────────┐
│ 检测是否与已有记忆   │
│ 存在矛盾           │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │ 冲突?     │
     ▼           ▼
   是          否
     │           │
     ▼           ▼
┌─────────────┐  正常添加
│ 冲突解决     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ 解决策略（由 LLM 判断）：     │
│ • override: 新记忆覆盖旧记忆  │
│ • merge: 合并两条记忆        │
│ • keep_both: 保留两条        │
│ • reject: 拒绝新记忆         │
└─────────────────────────────┘
```

### 13.2 冲突解决 Prompt

```python
RESOLVE_CONFLICT_PROMPT = """
检测到新记忆与已有记忆可能存在冲突，请判断并解决。

【已有记忆】
{existing_memory}

【新记忆】
{new_memory}

【冲突类型】
- 矛盾：两段信息直接对立
- 更新：新信息是对旧信息的更新/修正
- 补充：新信息是对旧信息的补充细节

【输出格式】
{{
    "conflict_type": "contradiction|update|supplement|none",
    "resolution": "override|merge|keep_both|reject",
    "merged_summary": "如果合并，给出合并后的摘要",
    "reason": "判断理由"
}}
"""
```

### 13.3 记忆更新流程

```python
class FuzzyMemoryGraph:
    
    async def update_memory(
        self,
        old_id: str,
        new_memory: FuzzyMemory
    ) -> None:
        """更新记忆（保持关联）"""
        old_memory = self._nodes[old_id]
        
        # 继承旧的关联边
        old_edges = self._edges.get(old_id, [])
        
        # 替换节点
        self._nodes[new_memory.id] = new_memory
        del self._nodes[old_id]
        
        # 迁移关联
        for edge in old_edges:
            if edge.source_id == old_id:
                edge.source_id = new_memory.id
            if edge.target_id == old_id:
                edge.target_id = new_memory.id
        
        self._edges[new_memory.id] = old_edges
        del self._edges[old_id]
```

---

## 十四、模糊记忆淘汰策略

### 14.1 触发条件

当模糊记忆图节点数超过 `fuzzy_max_nodes` 时触发淘汰。

### 14.2 淘汰算法

```python
class FuzzyMemoryGraph:
    
    def _evict(self) -> FuzzyMemory:
        """
        淘汰策略：综合权重
        
        score = weight × importance × access_factor
        
        其中：
        - weight: 时间衰减后的权重
        - importance: 原始重要性分数
        - access_factor: 访问频率加成 (1 + 0.1 × log(access_count + 1))
        """
        min_score = float('inf')
        evict_candidate = None
        
        for node in self._nodes.values():
            access_factor = 1 + 0.1 * math.log(node.access_count + 1)
            score = node.weight * node.importance * access_factor
            
            if score < min_score:
                min_score = score
                evict_candidate = node
        
        if evict_candidate:
            self._remove_node(evict_candidate.id)
        
        return evict_candidate
    
    def _remove_node(self, node_id: str) -> None:
        """移除节点及相关边和索引"""
        # 移除节点
        del self._nodes[node_id]
        
        # 移除相关边
        if node_id in self._edges:
            del self._edges[node_id]
        
        # 移除指向该节点的边
        for edges in self._edges.values():
            edges[:] = [e for e in edges if e.target_id != node_id]
```

---

## 十五、性能优化

### 15.1 LLM 调用优化

减少 LLM 调用次数的策略：

| 策略 | 说明 |
|-----|------|
| 批量处理 | 压缩时批量处理多条消息 |
| 缓存人设摘要 | 只在初始化时提取一次 |
| 懒加载 | 检索时才调用诊断 LLM |
| 并行调用 | 独立任务并行执行 |

```python
class MemoryAgent:
    
    async def process_batch(
        self,
        memories: list[PreciseMemory]
    ) -> tuple[FuzzyMemory, list[MemoryEdge]]:
        """批量处理：一次 LLM 调用完成压缩+关键词+关联"""
        prompt = BATCH_PROCESS_PROMPT.format(
            memories=self._format_memories(memories),
            existing_summaries=self._get_existing_summaries()
        )
        
        result = await self._llm.generate(prompt)
        
        # 解析结果，生成模糊记忆和关联
        ...
```

### 15.2 Token 计数

```python
import re

def count_tokens(text: str) -> int:
    """
    简单 token 计数（估算）
    
    规则：
    - 英文：约 4 字符 = 1 token
    - 中文：约 1.5 字符 = 1 token
    """
    # 分离中英文
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z0-9]', text))
    other = len(text) - chinese - english
    
    return int(chinese / 1.5 + english / 4 + other / 3)
```

### 15.3 索引优化

```python
class KeywordIndex:
    
    def __init__(self):
        self._index: dict[str, set[str]] = {}
        self._category_index: dict[str, set[str]] = {}
        self._lock = threading.RLock()  # 线程安全
    
    def add(self, memory_id: str, keywords: Keywords) -> None:
        with self._lock:
            ...
    
    def search(self, keywords: list[str], ...) -> list[str]:
        with self._lock:
            ...
```

---

## 十六、异步架构

### 16.1 异步流程

```python
class MemoryManager:
    
    async def add_message(self, role: str, content: str, ...) -> None:
        """添加消息（异步）"""
        # 1. 同步：创建精准记忆
        precise = self._create_precise_memory(role, content)
        
        # 2. 异步：校验和评估
        validation, importance = await asyncio.gather(
            self._agent.validate(precise),
            self._agent.judge_importance(precise, self._fuzzy.get_summaries())
        )
        
        if validation.should_reject:
            return
        
        precise.importance = importance.importance
        
        # 3. 同步：添加到工作记忆
        evicted = self._working.add(precise)
        
        # 4. 异步：处理淘汰的记忆
        if evicted:
            await self._process_evicted(evicted)
    
    async def _process_evicted(self, memories: list[PreciseMemory]) -> None:
        """异步处理淘汰的记忆"""
        # 并行执行
        await asyncio.gather(
            self._storage.save_messages(memories),
            self._compress_and_store(memories)
        )
```

### 16.2 后台任务

```python
class MemoryManager:
    
    def __init__(self, ...):
        ...
        self._background_tasks: set[asyncio.Task] = set()
    
    def _start_background_task(self, coro) -> None:
        """启动后台任务"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
    
    async def add_message(self, ...):
        ...
        # 后台保存，不阻塞
        if self._config.auto_save and self._should_save():
            self._start_background_task(self._save_async())
```

---

## 十七、生命周期管理

### 17.1 启动流程

```python
async def initialize(
    llm: LLM,
    system_prompt: str,
    config: MemoryConfig | None = None
) -> MemoryManager:
    """初始化记忆管理器"""
    manager = MemoryManager(llm, system_prompt, config)
    
    # 1. 加载持久化数据
    await manager.load()
    
    # 2. 提取人设摘要
    await manager._agent._extract_personality()
    
    return manager
```

### 17.2 关闭流程

```python
class MemoryManager:
    
    async def close(self) -> None:
        """关闭并清理资源"""
        # 1. 等待后台任务完成
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 2. 保存数据
        await self.save()
        
        # 3. 关闭数据库连接
        self._storage.close()
```

---

## 十八、测试策略

### 18.1 单元测试

| 模块 | 测试重点 |
|-----|---------|
| WorkingMemory | 容量限制、FIFO 淘汰、token 计数 |
| FuzzyMemoryGraph | 添加节点、建立边、权重衰减、图遍历 |
| KeywordIndex | 索引构建、关键词搜索、分类过滤 |
| PersistentStorage | CRUD 操作、数据恢复 |
| MemoryAgent | Prompt 构建、结果解析 |

### 18.2 集成测试

```python
import pytest
from dawn_shuttle_intelligence import LLM
from dawn_shuttle_superficial_thinking import MemoryManager

@pytest.fixture
async def memory_manager():
    llm = LLM(provider="mock", model="test")  # Mock LLM
    manager = MemoryManager(
        llm=llm,
        system_prompt="你是一个测试助手"
    )
    yield manager
    await manager.close()

@pytest.mark.asyncio
async def test_add_and_retrieve(memory_manager):
    # 添加消息
    await memory_manager.add_message("user", "我喜欢 Python")
    
    # 检索
    result = await memory_manager.retrieve("我的偏好")
    
    assert len(result.fuzzy_memories) > 0
    assert "Python" in result.fuzzy_memories[0].summary

@pytest.mark.asyncio
async def test_memory_compression(memory_manager):
    # 添加足够多的消息触发压缩
    for i in range(25):
        await memory_manager.add_message("user", f"消息 {i}")
    
    stats = memory_manager.get_stats()
    assert stats["fuzzy_count"] > 0  # 应该有模糊记忆

@pytest.mark.asyncio
async def test_weight_decay(memory_manager):
    # 添加消息并等待
    await memory_manager.add_message("user", "测试衰减")
    
    # 触发衰减
    await memory_manager.decay()
    
    # 验证权重降低
    ...
```

### 18.3 Mock LLM

```python
class MockLLM:
    """测试用 Mock LLM"""
    
    async def generate(self, prompt: str) -> str:
        # 根据提示词返回预设响应
        if "人设" in prompt:
            return json.dumps({
                "role": "测试助手",
                "expertise": ["测试"],
                "target_users": ["开发者"],
                "constraints": [],
                "valuable_memory_types": ["偏好"],
                "summary": "测试用助手"
            })
        elif "重要性" in prompt:
            return json.dumps({
                "importance": 0.7,
                "action": "add",
                "reason": "测试"
            })
        ...
```

### 18.4 测试覆盖率目标

| 类型 | 目标 |
|-----|------|
| 语句覆盖率 | ≥ 80% |
| 分支覆盖率 | ≥ 70% |
| 核心路径 | 100% |

---

## 十九、扩展点设计

### 19.1 存储后端抽象

```python
from abc import ABC, abstractmethod

class StorageBackend(ABC):
    """存储后端抽象"""
    
    @abstractmethod
    async def save_message(self, memory: PreciseMemory) -> None:
        ...
    
    @abstractmethod
    async def load_messages(self, ids: list[str]) -> list[PreciseMemory]:
        ...
    
    @abstractmethod
    async def save_fuzzy(self, memory: FuzzyMemory) -> None:
        ...
    
    @abstractmethod
    async def load_all_fuzzy(self) -> list[FuzzyMemory]:
        ...

class SQLiteStorage(StorageBackend):
    """SQLite 实现（默认）"""
    ...

class FileStorage(StorageBackend):
    """文件存储实现"""
    ...

# 用户可自定义
class CustomStorage(StorageBackend):
    """自定义存储"""
    ...
```

### 19.2 检索策略抽象

```python
class RetrievalStrategy(ABC):
    """检索策略抽象"""
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        fuzzy_graph: FuzzyMemoryGraph,
        index: KeywordIndex,
        top_k: int
    ) -> list[FuzzyMemory]:
        ...

class KeywordRetrieval(RetrievalStrategy):
    """关键词检索（默认）"""
    ...

class SemanticRetrieval(RetrievalStrategy):
    """语义检索（需嵌入模型）"""
    ...

class HybridRetrieval(RetrievalStrategy):
    """混合检索"""
    ...
```

### 19.3 压缩策略抽象

```python
class CompressionStrategy(ABC):
    """压缩策略抽象"""
    
    @abstractmethod
    async def compress(
        self,
        memories: list[PreciseMemory]
    ) -> FuzzyMemory:
        ...

class LLMCompression(CompressionStrategy):
    """LLM 压缩（默认）"""
    ...

class RuleCompression(CompressionStrategy):
    """规则压缩（无 LLM）"""
    ...

class SummaryCompression(CompressionStrategy):
    """摘要压缩"""
    ...
```

### 19.4 配置扩展

```python
@dataclass
class MemoryConfig:
    # ... 基础配置 ...
    
    # 扩展点
    storage_backend: type[StorageBackend] = SQLiteStorage
    retrieval_strategy: type[RetrievalStrategy] = KeywordRetrieval
    compression_strategy: type[CompressionStrategy] = LLMCompression
    
    # 自定义参数
    custom_params: dict = field(default_factory=dict)
```

### 19.5 钩子系统

```python
class MemoryHooks:
    """记忆系统钩子"""
    
    async def on_message_added(self, memory: PreciseMemory) -> None:
        """消息添加后"""
        pass
    
    async def on_memory_compressed(
        self,
        precise: list[PreciseMemory],
        fuzzy: FuzzyMemory
    ) -> None:
        """记忆压缩后"""
        pass
    
    async def on_memory_evicted(self, memory: FuzzyMemory) -> None:
        """记忆淘汰后"""
        pass
    
    async def on_retrieval(
        self,
        query: str,
        result: RetrievalResult
    ) -> None:
        """检索完成后"""
        pass

class MemoryManager:
    def __init__(self, ..., hooks: MemoryHooks | None = None):
        self._hooks = hooks or MemoryHooks()
    
    async def add_message(self, ...):
        ...
        await self._hooks.on_message_added(precise)
```

---

## 附录

### A. 权重衰减计算示例

```python
import math

def calculate_decay(initial_weight: float, hours: float, lambda_: float = 0.01) -> float:
    """
    计算衰减后的权重
    
    公式: w(t) = w₀ × exp(-λ × Δt)
    """
    return initial_weight * math.exp(-lambda_ * hours)

# 示例
w0 = 1.0
print(f"初始权重: {w0}")
print(f"1小时后: {calculate_decay(w0, 1):.3f}")   # 0.990
print(f"24小时后: {calculate_decay(w0, 24):.3f}") # 0.787
print(f"72小时后: {calculate_decay(w0, 72):.3f}") # 0.487
print(f"168小时后(一周): {calculate_decay(w0, 168):.3f}") # 0.186
```

### B. 相关研究参考

- [Memoria: Conversational Memory for LLMs](https://arxiv.org/html/2512.12686v1)
- [MemGPT/Letta Agent Memory](https://www.letta.com/blog/agent-memory)
- [MAGMA: Graph-based Agent Memory](https://shibuiyusuke.medium.com/graph-based-agent-memory-a-complete-guide-to-structure-retrieval-and-evolution-6f91637ad078)
- [Learning to Remember: A Concept-Based Memory System](https://arxiv.org/html/2412.15280)
