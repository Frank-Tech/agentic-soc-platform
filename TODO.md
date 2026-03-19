# TODO

## 1. 文档定位

这个文件用于持续记录平台后续待推进的事项。

维护方式：

1. 已完成的事项直接删除。
2. 新增事项按优先级加入对应分组。
3. 尽量记录“要做什么”，避免把这里写成背景说明文档。
4. 如果某项已经拆成多个子任务，优先保留可执行的子任务。

---

## 2. 高优先级

### 2.2 Artifact

1. 基于 Artifact 的内部资产查询
2. 基于 Artifact 的外部威胁情报查询
3. 基于 Artifact 的历史日志 pivot 查询
4. 基于 Artifact 的相似告警查询
5. 基于 Artifact 的图谱或关系查询

### 2.3 Enrichment

1. 增加 enrichment 查询接口
2. 增加 enrichment 更新接口
3. 增加按 provider/type 检索 enrichment 的接口
4. 增加 enrichment 来源追踪与时间线展示能力

---

## 3. 中优先级

### 3.1 接口模型统一化

1. 继续统一 MCP 列表接口的公共参数与返回风格
2. 收口 `list_*` 类接口中的重复过滤与序列化逻辑
3. 继续统一 `create_* + attach_*` 两步式 MCP 接口命名与描述文字
4. 在统一路由接口中继续统一 `target_type + target_id` 风格
5. 明确对象 ID、记录 row ID、运行记录 ID、定义名四类标识的命名边界

### 3.2 Playbook

1. 对 `execute_playbook` 增加 definition 名称校验或友好错误返回
2. 视需要增加按对象视角查询 playbook run 的更清晰别名接口
3. 评估是否需要为 playbook run 增加独立详情接口，而不是仅依赖 `list_playbook_runs`

### 3.3 Knowledge

1. 语义搜索接口
2. 按标签或场景批量检索
3. 将 Playbook/Agent 输出结果直接写入 Knowledge
4. 更清晰的知识生命周期，例如 `STORE`、`REMOVE`、`ACTIVE`、`EXPIRED`

### 3.4 结果沉淀方式

1. 原始字段保留源事实
2. Enrichment 承载扩展结果
3. AI 分析与 Playbook 输出优先沉淀为 Enrichment

---

## 4. 低优先级

### 4.1 Agent / Knowledge / Playbook 联动

1. Agent/Playbook 查询 Knowledge
2. Agent/Playbook 完成分析
3. 将高价值结构化结果写回 Enrichment 或 Knowledge
4. 后续 Agent 再次消费这些知识

### 4.2 Case

1. Case 视角的全景上下文查询
2. Case 时间线视图
3. Case 复盘资料结构化沉淀
4. Case 级别的自动摘要与交接信息生成

### 4.3 Alert

1. Alert 解释型 enrichment 模板
2. 告警误报原因结构化沉淀
3. 跨告警相似性分析
4. 规则解释与命中依据回填

### 4.4 Ticket

1. 工单状态同步任务完善
2. 工单与 Case 双向追踪能力
3. 工单同步失败重试与审计

### 4.5 AI Agent

1. LangGraph Playbook 标准模板
2. Agent 输出结构化写回 Enrichment
3. Agent 结合 Knowledge 做实时分析
4. Agent 调用 Artifact 相关工具做 pivot 分析

---

## 5. 后续维护原则

1. 领域逻辑尽量下沉到 `sirpapi.py` 等领域层
2. MCP 层尽量保持为参数 schema、对象路由、结果包装
3. 新能力优先围绕真实对象关系建模，不在 MCP 层虚构关系
4. 优先强化 Artifact、Enrichment、Knowledge、Playbook 之间的联动
5. 优先消除 MCP 接口命名歧义，尤其区分 definition、run、record、target object
