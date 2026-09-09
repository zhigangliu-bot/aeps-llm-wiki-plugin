<!-- 提示:本页是 plugin 自定义 reserved filename(OKF §8 index.md),无 frontmatter;若本批次未来加上 frontmatter,tags 示例务必 ≥ 6 条,避免 LLM 按 5 条填导致 WARN。详见 P3-4 修复。 -->

<!-- change history:
  - v0.6.4 (P0 issue #5): 删除硬编码占位 wikilink(Karpathy / ISO 26262 / S32G / S32K3 / LayerZero /
    Wormhole / 分析页 / 综合页 等),改为「*(暂无)*」骨架。aggregate-index.js 在 init 后会被用户
    触发,真实数据写入。
    之前:init 后用户工程 knowledge/index.md 末尾被追加真数据,前面占位保留,造成「占位 + 真数据」并存误导。
    现在:init 模板即干净,aggregate-index 重新生成时被覆盖为「真数据」+ 「空组 → *(暂无)*」。
    同时:Entities / Concepts / Analyses / Comparisons / Syntheses 节的 ### Person/Method/...
    H3 占位也删除(由 renderIndex 按 type 动态生成,避免双重 H3)。
-->
# 项目名 Wiki 主目录

> **plugin 版本**:0.6.4
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

---

## Entities({数量})

---

## Concepts({数量})

---

## Analyses({数量})

【按 `type: analysis` 页 list,仅列最近 10 条 + 归档链接。LLM 自动生成。】

---

## Comparisons({数量})

---

## Syntheses({数量})

---

## Maintenance

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 子类判定示例 + 命名飘检查规则:`../doc/design/design.md §4.4`(待写)
- 本文件由 SKILL.md 在每次 ingest / query 落档 / lint --fix 时增量更新,**不要手工编辑**
