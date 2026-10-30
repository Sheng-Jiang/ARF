# ADR-001: 面向下一代自主智能体的轻量化代码本体与确定性领域建模准则 (Lightweight Code-First Ontology & Deterministic Domain Modeling for AI Agents)

* **状态 (Status)**: 已采纳 (Accepted) · 全局强制执行标准 (Cross-Repo Architecture Standard)
* **提出时间 (Date)**: 2026-10-25
* **决策者 (Deciders)**: 姜胜 (Lead Architect), Antigravity AI
* **适用代码库 (Scope)**: 
  * `BidAgent` (下一代工程投标智能体 · 标书即 CPQ)
  * `Architect` (FilterArchitect · 工业过滤材料物理数字孪生与选型系统)
  * `ARF` (AI Relevance Factor · AI 产业价值链与估值监控系统)
  * 以及未来所有基于多智能体（Multi-Agent System）构建的行业解决方案
* **废止/替代 (Supersedes)**:
  * 传统重型企业架构文档范式（TOGAF / ArchiMate 静态文档“书架资产”）
  * 学院派语义网学术技术栈（W3C RDF / OWL / SPARQL / 三元组知识图谱数据库）
  * “无模型狂奔”的无状态纯概率大模型生成范式（Model-Free Stochastic Generation）

---

## 1. 背景与核心问题陈述 (Context & Problem Statement)

### 1.1 现实反思：南方电网与中兴通讯架构困局的血泪教训
在对南方电网（CSG-EA）与中兴通讯（ZTE 硬件工程诊断报告）的企业架构实践进行深度复盘后，我们确立了一个不可动摇的先验事实：
1. **“让人类阅读并理解复杂的企业架构模型”是彻底反人性的，注定失败**：巨型组织试图通过编写几十页《白皮书》、《变革场景方案》和多层 Visio/ArchiMate 蓝图来管控企业，最终陷入“认知过载、审批时滞 40 天、一线看不懂也不想看、模型在库里发霉、代码在库外野蛮生长”的巴别塔悲剧；
2. **“试图把一线业务人员培训成 TOGAF 架构师”已被历史证明是一场悲壮的西西弗斯式推石上山**：一线人员需要的是即时解决现场问题，强迫其学习元模型分类学只会带来巨大的组织抗拒与虚假合规。

### 1.2 另一端的致命深渊：“无模型”的大模型幻觉
然而，如果在开发 AI Agent 时彻底走向另一个极端——“既然 LLM 能读懂一切，就不需要任何建模，全靠 Prompt + RAG + 概率生成”——系统会立即在工业与复杂工程级场景中当场崩溃：
* 经济标与工程算术出现随机幻觉（大模型不会算加减乘除）；
* 跨章节承诺自相矛盾、资质证明与技术选型脱节、触发致命废标红线；
* 工业选型推荐违背流体力学、热力学与化学机理，造成严重工程事故；
* 投资与估值推演缺乏因果逻辑传导链，退化为无意义的情绪文字。

### 1.3 核心共识：从“面向人类的文档架构”跃迁为“面向 Agent 的计算底座”
**建模（Modeling）在智能体时代不是过时了，而是其使用者彻底从“人类”变成了“Agent”。**
我们需要一套既彻底抛弃“学术装逼与繁文缛节”，又能赋予 Agent 100% 确定性、因果推理和安全护栏的**下一代代码化本体（Code-First Operational Ontology）与领域建模体系**。

---

## 2. 核心架构决策 (Architectural Decisions)

我们确立以下五大根本原则，作为所有代码库进行领域建模与图谱设计的统一准则：

### 原则一：模型隐形化（Invisible Model Principle）
> **人类面对大白话与原生交互界面，模型留给 Agent 作为计算世界模型（World Model）。**

* 严禁要求任何终端用户（投标工程师、工业买家、投资研究员）去理解 ArchiMate、UML 或本体元模型；
* 交互界面必须符合人类本能（`BidAgent` 的本地文件夹直驱、`Architect` 的 6 步直觉向导、`ARF` 的温度计看板与一键运行）；
* 模型全部隐藏在引擎盖之下，充当 Agent 的**动作空间（Action Space）**、**因果图谱（Causal Graph）**与**形式化验证器（Formal Verifier）**。

### 原则二：坚决采用“无公害轻量图谱技术栈”（The Anti-Bullshit Tech Stack）
> **彻底剔除 W3C 学院派重型设施，全面采用 Python/TS 现代数据栈实现本体与图谱。**

* **绝对禁止引入 (FORBIDDEN)**：
  * Neo4j, GraphDB, Virtuoso, Stardog 等重型图数据库集群与三元组库；
  * OWL, RDF, SPARQL 等复杂描述逻辑（DL）推导引擎；
  * 任何需要独立运维、产生高昂认知阻抗与网络 IO 开销的外部图服务。
* **强制统一采用 (MANDATED)**：
  * **模式定义与验证**：`Pydantic v2` (Python) / `TypeScript interface` + `Zod` (Node.js)。所有实体必须具有严格的强类型约束和只读不可变设计；
  * **内存图计算与拓扑推理**：Python 内置 `networkx`。用于实体之间的 DAG 依赖分析、最短路径查找、多跳级联影响分析及环路检测；
  * **存储与持久化**：`DuckDB` (支持嵌入式分析与快照) / `SQLite` (支持递归 CTE) / `YAML` / `JSON` (版本化纯文本，支持 Git 追踪与 Agent 双向读写)；
  * **数据契约严密性**：所有 Pydantic 模型必须声明 `model_config = ConfigDict(extra="forbid")`，拼写错误即语法错误，严禁静默容忍。

### 原则三：动力学四元本体模型（The 4-Element Kinetic Ontology Standard）
> **借鉴 Palantir 核心思想，所有垂直领域模型必须收敛为四元结构，坚决不做纯静态的词汇表。**

无论是招投标工程、工业过滤材料、还是金融价值链，每个领域模型（DPSM）必须显式具备以下四要素：
1. **构件实体 (Components / Objects)**：领域名词与资产全集（技术标选配树 / 滤料材质库 / 产业链公司池）；
2. **推导规则 (Sizing / Formulas)**：数学与物理映射公式（参数如何转化为工程量 / 工况如何转化为材质指标）；
3. **级联约束 (Compliance / Invariant Links)**：因果边与合规门禁（选了 A 构件必须在商务标中级联要求资质 B / 超温即一票否决）；
4. **行动定价 (Pricing / Actions)**：商业后果与写回（构件如何套用定额并闭合税费 / 下单跳转与工单写回）。

### 原则四：确定性计算与概率推理物理隔离（Deterministic Isolation）
> **严禁大模型做算术，严禁大模型仲裁硬性合规门禁。**

* **概率归 LLM**：语义理解、非结构化长文本抽取、专业工程文字润色、方案答辩起草交由大模型；
* **确定性归引擎**：
  * 金额、税率、工程量合价必须由确定性代码（如 `openpyxl` / `boq_engine.py` / 专用定价函数）计算；
  * 废标红线、物理极限越界、合规门禁必须由确定性代码拦截（`Guards Must Bite`），一旦触碰当场阻断，严禁交给概率模型“商量”。

### 原则五：数据可追溯与反向证明树（Provenance & Proof Tree）
> **每个输出数字与决策，必须在模型图谱中具备可解释的因果溯源。**

* 模型中的每一个关键字段（如工程单价、推荐材质、泡沫评分）必须挂载 `Provenance`（来源：招标原文出处 / 国标规范条目 / 财报原始字段 / 专家假设）；
* Agent 的每一个最终结论，必须能够沿着图谱边（Edges）反向生成**形式化证明树（Proof Tree）**，确保交付给高管的决策备忘录具备绝对的法律和审计可信度。

---

## 3. 各核心代码库落地映射指南 (Repository Directives)

### 3.1 `BidAgent` (下一代工程投标智能体)
* **核心本体载体**：`bidagent/core/dpsm/` (Domain Product/Service Model).
* **必须执行的架构动作**：
  1. **内存图化**：使用 `networkx.DiGraph` 加载 DPSM 中的 `components`、`sizing` 与 `compliance`，在方案生成前执行拓扑排序，自动化排查“选了设备却漏配电、要了资质却无证书”的断链问题；
  2. **逆向蒸馏 (Harvesting)**：实现 `DPSM Harvester Agent`，从历史中标标书与清单 Excel 中反向提炼垂直行业 DPSM 初稿，降低手写 YAML 门槛；
  3. **确定性算术底线**：继续严格执行 `boq_engine.py` 规则，严禁大模型改动经济标计算公式；
  4. **双厂商对抗**：起草与终审专家必须物理隔离调用不同厂商基础模型。

### 3.2 `Architect` (FilterArchitect · 工业过滤材料系统)
* **核心本体载体**：`shared/materials.json` + `shared/industry-map.json` + 飞书 PIM (`材料主表`/`产品主数据`).
* **必须执行的架构动作**：
  1. **规则网络升维 (Constraint Network)**：将单纯的温度/耐酸碱属性打分，升级为物理工况约束求解器（CSP）。当烟气成分存在高水解或酸露点风险时，由代码引擎执行逻辑剪枝，而非由大模型模糊猜测；
  2. **与 BidAgent 的横向击穿**：`Architect` 的材质库与报价模型天然作为 `BidAgent` 在环保除尘领域的标准 DPSM 构件库，共享数据模式；
  3. **PIM 单一真实源**：飞书 Bitable 负责发布态维护，系统通过强契约解析并构建本地运行时物理本体。

### 3.3 `ARF` (AI Relevance Factor · 投资总监驾驶舱)
* **核心本体载体**：`config/value_chain.yaml` + `arf/value_chain.py` + `data/arf.db` (DuckDB).
* **必须执行的架构动作**：
  1. **因果价值网拓扑**：将静态的 5-layer 蛋糕扩展为有向传导因果图（如 `TSMC ──► NVDA ──► Hyperscalers ──► Apps`），在 DuckDB 中建立拓扑关系视图；
  2. **反事实压力测试 (Counterfactual Simulation)**：Agent 基于因果图谱进行扰动推演（如某上游环节涨价或出货受阻对下游公司 V_score 的传导效应）；
  3. **不可变快照审计**：严格遵循 DuckDB 单调递增 `snapshot_revisions` 原则，所有因果评分必须带时间戳与版本溯源。

---

## 4. 实施与符合性验证清单 (Compliance & Verification Checklist)

任何新增模块或垂直领域扩展，必须通过以下架构审查检查点（Gate Review）：

* [ ] **No-OWL 审查**：是否误引入了 RDF/OWL/SPARQL/Neo4j 等沉重学术依赖？（一票否决）
* [ ] **Strict Typing 审查**：核心领域模型是否全部通过 Pydantic v2 / TypeScript 严格定义？是否设置了 `extra="forbid"`？
* [ ] **Deterministic Math 审查**：涉及金额、税费、工程量、估值公式的逻辑，是否有独立的 Python 单元测试证明**未使用任何 LLM 调用**？
* [ ] **Guards Must Bite 审查**：针对废标点、越界选型、风控红线，是否配备了“在违规时当场变红阻断”的红线测试用例？
* [ ] **Invisible UX 审查**：终端用户界面是否完全屏蔽了底层架构术语与元模型概念？用户是否只需要使用日常业务语言交互？

---

## 5. 预期成效与演进路线 (Consequences & Evolution)

### 正向收益 (Positive Consequences)
1. **开发敏捷性爆发**：彻底摆脱传统 EA 的文档官僚主义，模型改动直接体现为 Git Commit 和代码测试，所见即所得；
2. **Agent 确定性与工业级可靠**：Agent 不再是天马行空胡说八道的“文学家”，而是在形式化轨道上高速奔跑的“自动化精密机床”；
3. **资产跨行业极速复用**：沉淀下来的 DPSM 和物理材料模型成为公司最值钱的代码级数字孪生资产，换一个行业只需配置一份新 YAML。

### 伴随代价与应对 (Trade-offs & Mitigations)
* **前期建模需要领域深度（Domain Depth）**：定义 Pydantic Schema 和约束网络需要真正的行业专家介入（造价总工、除尘专家）。
  * *应对策略*：采用 Agent 辅助提炼（Reverse Harvesting）技术，让 Agent 读历史文档提炼出 80% 的模型草案，人只负责最后的 20% 审校。
