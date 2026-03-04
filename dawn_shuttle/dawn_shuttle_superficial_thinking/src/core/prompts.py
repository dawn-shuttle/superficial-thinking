"""Prompt 模板定义"""

# 人设提取
EXTRACT_PERSONALITY_PROMPT = """从以下 LLM 人设/系统提示词中提取核心要点。

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

只输出 JSON，不要其他内容。"""

# 记忆校验
VALIDATE_MEMORY_PROMPT = """校验记忆内容是否与 LLM 人设约束一致。

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
    "valid": true或false,
    "issues": ["问题1", "问题2"],
    "should_reject": true或false,
    "reason": "拒绝原因（如适用）"
}}

只输出 JSON，不要其他内容。"""

# 重要性判断
JUDGE_IMPORTANCE_PROMPT = """你是一个记忆评估专家。根据 LLM 人设和已有记忆，判断新记忆的重要性。

【LLM 人设核心要点】
{personality_summary}

【已有记忆摘要】
{existing_summaries}

【新记忆内容】
角色: {new_role}
内容: {new_content}

【评估维度】
1. 人设相关性：这条记忆对履行人设职责有帮助吗？（0-1）
2. 新颖性：是否是人设需要但尚未记录的信息？（0-1）
3. 冗余性：是否可由已有记忆推断？（0-1）

【输出格式】
{{
    "importance": 0.0到1.0之间的数值,
    "persona_relevance": 0.0到1.0之间的数值,
    "novelty": 0.0到1.0之间的数值,
    "redundancy": 0.0到1.0之间的数值,
    "action": "add或update或skip",
    "reason": "判断理由",
    "update_target": "如果需要更新，指明更新哪条记忆的ID，否则为null"
}}

只输出 JSON，不要其他内容。"""

# 关键词提取
EXTRACT_KEYWORDS_PROMPT = """从以下记忆内容中提取关键词。

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
    "category": "偏好或事件或事实或决策"
}}

只输出 JSON，不要其他内容。"""

# 记忆压缩
COMPRESS_MEMORY_PROMPT = """将以下多条精准记忆压缩为一条模糊记忆。

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

只输出 JSON，不要其他内容。"""

# 关联判断
RELATE_MEMORY_PROMPT = """判断新记忆与现有记忆之间的关联关系。

【新记忆】
ID: {new_id}
摘要: {new_summary}

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
            "weight": 0.0到1.0之间的数值,
            "reason": "判断理由"
        }},
        ...
    ]
}}

如果没有明显关联，返回空列表 {{"relations": []}}
只输出 JSON，不要其他内容。"""

# 查询分析
ANALYZE_QUERY_PROMPT = """分析用户查询，判断需要哪些记忆支持。

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
    "need_memory": true或false,
    "reason": "为什么需要/不需要",
    "memory_types": ["偏好", "事件", "事实", "决策"],
    "keywords": ["主关键词1", "主关键词2"],
    "related_keywords": ["扩展词1", "扩展词2"],
    "time_range": {{"start": "...", "end": "..."}}或null,
    "confidence": 0.0到1.0之间的数值
}}

只输出 JSON，不要其他内容。"""

# 记忆诊断
DIAGNOSE_MEMORY_PROMPT = """对候选记忆进行诊断，确保不遗漏或误解。

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
            "relevance": 0.0到1.0之间的数值,
            "reason": "相关性理由"
        }}
    ],
    "need_precise": ["需要加载精准版本的ID"],
    "need_precise_reason": "为什么需要精准版本",
    "possibly_missing": ["可能遗漏的记忆类型"],
    "confidence": 0.0到1.0之间的数值
}}

只输出 JSON，不要其他内容。"""

# 冲突检测
RESOLVE_CONFLICT_PROMPT = """检测到新记忆与已有记忆可能存在冲突，请判断并解决。

【已有记忆】
{existing_memory}

【新记忆】
{new_memory}

【冲突类型】
- contradiction: 两段信息直接对立
- update: 新信息是对旧信息的更新/修正
- supplement: 新信息是对旧信息的补充细节
- none: 无冲突

【输出格式】
{{
    "conflict_type": "contradiction或update或supplement或none",
    "resolution": "override或merge或keep_both或reject",
    "merged_summary": "如果合并，给出合并后的摘要",
    "reason": "判断理由"
}}

只输出 JSON，不要其他内容。"""

# 批量处理
BATCH_PROCESS_PROMPT = """批量处理记忆：压缩、提取关键词、判断关联。

【人设要点】
{personality_summary}

【已有记忆摘要】
{existing_summaries}

【待处理记忆列表】
{memories}

【处理任务】
1. 压缩为一条模糊记忆摘要
2. 提取知识三元组
3. 提取关键词
4. 判断与已有记忆的关联

【输出格式】
{{
    "summary": "压缩后的一句话概括",
    "triples": [
        {{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9}}
    ],
    "keywords": {{
        "primary": ["关键词1", "关键词2"],
        "secondary": ["扩展词1"],
        "entities": ["实体1"],
        "category": "分类"
    }},
    "relations": [
        {{
            "target_id": "已有记忆ID",
            "relation": "关联类型",
            "weight": 0.8,
            "reason": "理由"
        }}
    ]
}}

只输出 JSON，不要其他内容。"""
