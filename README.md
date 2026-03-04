# Superficial Thinking

基于推理的 LLM 记忆层 - 一个轻量级、高效的记忆管理系统。

## 概述

Superficial Thinking 是一个为 LLM 应用设计的记忆层，通过分层记忆架构和智能压缩，在保持上下文连贯性的同时大幅降低 API 调用成本。

### 核心特性

- **分层记忆架构**：工作记忆（精准）→ 模糊记忆（压缩）→ 持久化存储
- **低成本设计**：运行时零 LLM 调用，仅在批量压缩时调用
- **关键词索引**：支持部分匹配的快速检索
- **异步优先**：完全异步设计，支持高并发场景
- **持久化存储**：SQLite 后端，自动保存与恢复

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    初始化阶段                            │
│  加载持久化记忆 → 关键词索引构建                         │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    运行时（无 LLM 调用）                 │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  工作记忆     │    │  模糊记忆     │                   │
│  │  (精准、近期) │    │  (压缩、关联) │                   │
│  │  直接添加     │    │  关键词索引   │                   │
│  └──────────────┘    └──────────────┘                   │
│         ↓ 达到上限触发批量压缩（1次 LLM）               │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              query_memory 工具（LLM 按需调用）          │
│  关键词检索 → LLM 汇总 → 流畅语段返回                   │
└─────────────────────────────────────────────────────────┘
```

## 安装

```bash
pip install dawn_shuttle_superficial_thinking
```

## 快速开始

```python
import asyncio
from dawn_shuttle.dawn_shuttle_intelligence import OpenAICompatibleProvider
from dawn_shuttle.dawn_shuttle_superficial_thinking import MemoryManager, MemoryConfig

async def main():
    # 初始化 LLM 提供者
    provider = OpenAICompatibleProvider(
        api_key="your-api-key",
        base_url="https://api.example.com/v1"
    )
    
    # 创建记忆管理器
    config = MemoryConfig(
        db_path="memory.db",
        working_max_messages=20,  # 工作记忆容量
    )
    memory = MemoryManager(
        llm=provider,
        system_prompt="你是一个智能助手。",
        config=config,
        model="gpt-4"
    )
    
    # 初始化
    await memory.initialize()
    
    # 添加消息（无 LLM 调用）
    await memory.add_message("user", "我是张三，我喜欢 Python")
    await memory.add_message("assistant", "你好张三！")
    
    # 检索相关记忆（无 LLM 调用）
    result = await memory.retrieve("用户的编程偏好")
    for mem in result.fuzzy_memories:
        print(mem.summary)
    
    # 按需查询（有 LLM 调用，返回流畅语段）
    answer = await memory.query_memory("张三喜欢什么？")
    print(answer)
    
    # 获取上下文
    context = memory.get_context()
    
    # 关闭
    await memory.close()

asyncio.run(main())
```

## LLM 调用优化

| 场景 | 传统方案 | 本方案 |
|------|----------|--------|
| 每条消息 | 1-2 次 | **0 次** |
| 检索 | 2 次 | **0 次** |
| 压缩 | 每次 1 条 | **批量 1 次** |
| 按需查询 | - | **1-2 次** |

## 配置说明

```python
@dataclass
class MemoryConfig:
    # 工作记忆
    working_max_messages: int = 20      # 最大消息数量
    working_max_tokens: int = 4000      # 最大 token 数量
    
    # 模糊记忆
    fuzzy_max_nodes: int = 100          # 最大节点数
    fuzzy_decay_lambda: float = 0.01    # 权重衰减率
    
    # 检索
    retrieval_top_k: int = 10           # 返回记忆数量
    retrieval_candidates: int = 20      # 候选数量
    retrieval_threshold: float = 0.3    # 相关性阈值
    
    # 持久化
    db_path: str = "memory.db"          # 数据库路径
    auto_save: bool = True              # 自动保存
    save_interval: int = 10             # 保存间隔
    
    # 压缩
    compress_batch_size: int = 5        # 压缩批大小
```

## API 参考

### MemoryManager

主入口类，管理整个记忆系统。

#### 方法

| 方法 | 说明 | LLM 调用 |
|------|------|----------|
| `initialize()` | 初始化记忆系统 | 0-1 次 |
| `add_message(role, content)` | 添加消息 | 0 次 |
| `retrieve(query)` | 检索相关记忆 | 0 次 |
| `query_memory(query)` | 按需查询（工具） | 1-2 次 |
| `get_context()` | 获取对话上下文 | 0 次 |
| `get_stats()` | 获取统计信息 | 0 次 |
| `close()` | 关闭并保存 | 0 次 |

### 核心类型

```python
# 精准记忆（工作记忆中的原始消息）
@dataclass
class PreciseMemory:
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    importance: float
    metadata: dict[str, Any]

# 模糊记忆（压缩后的摘要）
@dataclass
class FuzzyMemory:
    id: str
    summary: str                    # 压缩摘要
    triples: list[Triple]           # 知识三元组
    keywords: Keywords              # 关键词
    weight: float                   # 权重（时间衰减）
    importance: float
    source_ids: list[str]           # 来源记忆ID

# 检索结果
@dataclass
class RetrievalResult:
    fuzzy_memories: list[FuzzyMemory]
    precise_memories: list[PreciseMemory]
    confidence: float
    reason: str
```

## 依赖

- Python >= 3.10
- dawn_shuttle_intelligence (LLM 接口)

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check .
mypy .
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！