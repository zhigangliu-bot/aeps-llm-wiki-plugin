<!-- 提示:本页是 plugin 自定义 reserved filename(OKF §8 index.md),无 frontmatter;若本批次未来加上 frontmatter,tags 示例务必 ≥ 6 条,避免 LLM 按 5 条填导致 WARN。详见 P3-4 修复。 -->
# 项目名 Wiki 主目录

> **plugin 版本**:0.6.0
> **最近更新**:2026-09-04T10:30:00Z
> **自动生成**:本文件由 `/aeps-llm-wiki-init` 与 `/aeps-llm-wiki-ingest` 维护,不要手工编辑。
>
> 本文件无 frontmatter(OKF §3.1 reserved filename);本文件即 OKF §8 规定的 index.md。

---

## Overview

【一句话总览本项目 wiki 主题。】

参见 [overview](./overview.md) 查看大图。

---

## Sources({数量})

【按 frontmatter `resource` 路径解析的 `raw/{subdir}/` 分组输出;子目录名去掉 `\d+_` 编号前缀。每条用 `[[wikilink|alias]]` 裸文件名 + title 别名格式,行末直接展示 frontmatter 的 `status` 与 `tags`(不做 emoji 包装,纯枚举值);无法解析 resource 路径的 source 归到 `### 其他`。LLM / 脚本生成,详见 `scripts/aggregate-index.js`。】

### 功能安全 ({数量})

- [[iso26262|ISO 26262:2018 功能安全标准]] —— ISO 26262 道路车辆功能安全国际标准第 2 版。 [stable] <span style="color:gray">#功能安全 #ISO #标准</span>

### 芯片 ({数量})

- *(暂无)*

### 其他 ({数量})

- *(暂无)*

---

## Entities({数量})

### Person({数量})

- [Andréj Karpathy](./entities/person/andrej-karpathy.md) —— 前特斯拉 AI 总监、OpenAI 创始成员。<span style="color:gray">#人物 #AI #教育者</span>

### Organization({数量})

- *(暂无)*

### Project({数量})

- *(暂无)*

### Product({数量})

- *(暂无)*

### Event({数量})

- *(暂无)*

### Place({数量})

- *(暂无)*

### Other({数量})

- *(暂无)*

---

## Concepts({数量})

### Theory({数量})

- [LLM Wiki 模式](./concepts/theory/llm-wiki.md) —— 由 Andréj Karpathy 提出的基于 LLM 长期维护个人知识库的方法论。<span style="color:gray">#LLM #知识管理 #方法论</span>

### Method({数量})

- *(暂无)*

### Field({数量})

- *(暂无)*

### Phenomenon({数量})

- *(暂无)*

### Standard({数量})

- *(暂无)*

### Term({数量})

- *(暂无)*

### Other({数量})

- *(暂无)*

---

## Analyses({数量})

【按 `type: analysis` 页 list,仅列最近 10 条 + 归档链接。LLM 自动生成。】

- [S32G vs NXP S32K3 在车身控制器选型上的权衡](./analyses/2026-09-04-s32g-vs-s32k3.md) —— 基于 wiki 已有 S32G / S32K3 实体页与功能安全概念页的综合推演。<span style="color:gray">#芯片选型</span>

---

## Comparisons({数量})

- [LayerZero vs Wormhole 跨链机制对比](./comparisons/layerzero-vs-wormhole.md) —— 两条主流跨链桥实现机制的安全模型、信任假设、性能与生态差异。<span style="color:gray">#跨链桥</span>

---

## Syntheses({数量})

- [汽车功能安全体系综合](./syntheses/automotive-functional-safety.md) —— 整合 wiki 内 ISO 26262 / ASIL 分解 / 硬件架构度量 / 软件单元测试等所有相关概念的综合页。<span style="color:gray">#功能安全 #综合</span>

---

## Maintenance

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 子类判定示例 + 命名飘检查规则:`../doc/design/design.md §4.4`(待写)
- 本文件由 SKILL.md 在每次 ingest / query 落档 / lint --fix 时增量更新,**不要手工编辑**
