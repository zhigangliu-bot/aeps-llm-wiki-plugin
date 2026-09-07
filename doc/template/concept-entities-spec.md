

* **Concepts（概念）** ：指抽象的类别、领域术语、方法论或通用定义。它们回答的是“ **这是什么类型的知识？** ”
* **Entities（实体）** ：指现实或系统中的具象存在（特定的人、事物、组织、事件或产品）。它们回答的是“ **具体存在着什么？** ”

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

## 2. Entities 7 子类骨架建议(差异化模板)

| 子类 | 模板文件 | 推荐 H2 骨架 |
|---|---|---|
| `entity.person`       | `page-entity-person.md`       | 代表工作 / 关键思想 / 主要贡献 / 影响 |
| `entity.organization` | `page-entity-organization.md` | 业务范围 / 核心产品 / 关键人物 / 历史沿革 |
| `entity.project`      | `page-entity-project.md`      | 项目目标 / 范围 / 阶段 / 关键里程碑 / 团队 / 干系人 |
| `entity.product`      | `page-entity-product.md`      | 产品定位 / 核心特性 / 适用场景 / 竞品对照 / 版本演进 |
| `entity.event`        | `page-entity-event.md`        | 会议概览 / 时间地点 / 主题 / 关键演讲 / 重要发布 |
| `entity.place`        | `page-entity-place.md`        | 地理位置 / 历史 / 产业意义 / 相关组织 / 设施 |
| `entity.other`        | `page-entity-other.md`        | 不强制 H2 骨架;LLM 按资料特点自由组织;如常用结构重复出现,应新增子类 |

> **模板文件**:`doc/template/page-entity-{person,organization,project,product,event,place,other}.md`,7 个差异化骨架,`gen-page.js` 按 `entity.*` subtype 自动选模板(详见 `scripts/gen-page.js` 的 `tplName` 映射)。
>
> **历史背景**:早期版本曾让 6 个子类共用 `page-entity-person.md` 骨架,但 `## 代表工作 / ## 关键思想` 仅适合 `person`,对 `event / organization / project / product / place` 都不适用。现已拆分 7 个差异化模板,`gen-page.js` 按 subtype 自动映射。

## 2. Concept 子类枚举

| 值             | 含义          | 例子                                           |
| -------------- | ------------- | ---------------------------------------------- |
| `theory`     | 理论          | Continental V 模型、Why-loop                   |
| `method`     | 方法 / 实践   | 单元级别需求、虚拟线缆、EcuC-as-Code           |
| `field`      | 领域          | SDV、ADAS、Agentic                             |
| `phenomenon` | 现象 / 问题   | automotive-switch-standardization、Vision-Zero |
| `standard`   | 标准 / 规范   | TSN、ISO 26262、ISO 21434                      |
| `term`       | 术语 / 概念词 | AaaS、MaaS、Spec-Driven-Development            |
| `other`      | 兜底          | 不属于上述 6 类的概念                          |
