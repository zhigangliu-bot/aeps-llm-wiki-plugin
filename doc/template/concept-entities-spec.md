
* **Concepts(概念)**:指抽象的类别、领域术语、方法论或通用定义。它们回答的是"**这是什么类型的知识?**"
* **Entities(实体)**:指现实或系统中的具象存在(特定的人、事物、组织、事件或产品)。它们回答的是"**具体存在着什么?**"

> **v0.5.7 变更**:7 子类不再使用差异化 H2 骨架模板(已删除 `page-entity-{person,organization,project,product,event,place,other}.md` 与 `page-concept-{theory,method,field,phenomenon,standard,term,other}.md` 共 14 个文件);统一走 [`page-entity.md`](page-entity.md) / [`page-concept.md`](page-concept.md) 通用模板。子类差异通过 `type` 字段 / `aliases` / `tags` / 自由正文组织,**不**用 H2 节名体现。详见 `CHANGELOG.md`。

## 1. Entities 子类枚举

| 值               | 含义               | 例子                                         |
| ---------------- | ------------------ | -------------------------------------------- |
| `person`       | 个人               | Stefany-Chourakorn、Peter-Schiefer           |
| `organization` | 组织               | IEEE、Infineon、Vector、Continental          |
| `project`      | 项目 / 计划        | AES 2026、Automotive-Ecosystem-Summit-2026   |
| `product`      | 产品 / 工具 / 芯片 | AURIX™、VectorCAST、PREEvision、CANoe       |
| `event`        | 事件 / 会议        | IEEE Ethernet Day 2024、2026百人会、GTC 2026 |
| `place`        | 地点               | Munich、上海、张家口                         |
| `other`        | 兜底               | 不属于上述 6 类的实体                        |

## 2. Entities 7 子类共用通用骨架(v0.5.7 起)

| 子类 | type 取值 | 模板文件 |
|---|---|---|
| `entity.person` | `entity.person` | [`page-entity.md`](page-entity.md) |
| `entity.organization` | `entity.organization` | [`page-entity.md`](page-entity.md) |
| `entity.project` | `entity.project` | [`page-entity.md`](page-entity.md) |
| `entity.product` | `entity.product` | [`page-entity.md`](page-entity.md) |
| `entity.event` | `entity.event` | [`page-entity.md`](page-entity.md) |
| `entity.place` | `entity.place` | [`page-entity.md`](page-entity.md) |
| `entity.other` | `entity.other` | [`page-entity.md`](page-entity.md) |

> **子类差异如何体现**:不通过 H2 节名,而是通过 `type: entity.<subtype>` 字段(type 是 schema,不是 layout 指令)+ `aliases`(常用缩写 / 同义词,如 `[[AURIX]]` / `[[英飞凌]]` / `[[慕尼黑]]`)+ `tags` 6 轴字典 + LLM 自由正文的内部逻辑组织。
>
> **历史背景**:早期版本曾让 6 个子类共用 `page-entity-person.md` 骨架,后拆为 7 个差异化模板;v0.5.7 再合并回 1 个通用模板。`gen-page.js` 按 `entity.<subtype>` 自动选 `page-entity.md`(详见 [`scripts/gen-page.js`](../../scripts/gen-page.js) L261-269)。

## 3. Concept 子类枚举

| 值             | 含义          | 例子                                           |
| -------------- | ------------- | ---------------------------------------------- |
| `theory`     | 理论          | Continental V 模型、Why-loop                   |
| `method`     | 方法 / 实践   | 单元级别需求、虚拟线缆、EcuC-as-Code           |
| `field`      | 领域          | SDV、ADAS、Agentic                             |
| `phenomenon` | 现象 / 问题   | automotive-switch-standardization、Vision-Zero |
| `standard`   | 标准 / 规范   | TSN、ISO 26262、ISO 21434                      |
| `term`       | 术语 / 概念词 | AaaS、MaaS、Spec-Driven-Development            |
| `other`      | 兜底          | 不属于上述 6 类的概念                          |

## 4. Concept 7 子类共用通用骨架(v0.5.7 起)

| 子类 | type 取值 | 模板文件 |
|---|---|---|
| `concept.theory` | `concept.theory` | [`page-concept.md`](page-concept.md) |
| `concept.method` | `concept.method` | [`page-concept.md`](page-concept.md) |
| `concept.field` | `concept.field` | [`page-concept.md`](page-concept.md) |
| `concept.phenomenon` | `concept.phenomenon` | [`page-concept.md`](page-concept.md) |
| `concept.standard` | `concept.standard` | [`page-concept.md`](page-concept.md) |
| `concept.term` | `concept.term` | [`page-concept.md`](page-concept.md) |
| `concept.other` | `concept.other` | [`page-concept.md`](page-concept.md) |

> **子类差异如何体现**:同 entity 7 子类 —— 通过 `type` 字段、`aliases`(术语页强推荐,如 `[[AaaS]]` / `[[算法即服务]]`)、`tags`、`stale_after`(标准类默认 +5 年;其它 +1 年)、LLM 自由正文。
>
> **历史背景**:同 entity —— 早期版本曾拆分 7 个差异化模板,`## 核心原则` / `## 核心思想` / `## 领域范畴` / `## 现象描述` / `## 标准概述` / `## 定义` 各自仅适合单一子类;v0.5.7 合并回 1 个通用模板。`gen-page.js` 按 `concept.<subtype>` 自动选 `page-concept.md`。
