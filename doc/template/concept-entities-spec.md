

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
