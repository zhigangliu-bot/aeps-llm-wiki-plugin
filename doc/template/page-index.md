<!-- 提示:本页是 plugin 自定义 reserved filename(OKF §8 index.md),无 frontmatter;若本批次未来加上 frontmatter,tags 示例务必 ≥ 6 条,避免 LLM 按 5 条填导致 WARN。详见 P3-4 修复。 -->

<!-- change history:
  - v0.6.7 (PR-B #28/#31): 行结构契约 —— 每行 `[title](link) —— description [status]`,默认不渲染
    行尾 `<span style="color:gray">#tag</span>` tags(避免 #28 灰底冲淡 description)。`tags` 字段在
    `frontmatter.tags` 读,不在 list 行渲染;启用 `--show-tags` CLI 开关时输出灰色 `<span>` 包装。
    6 处 tags 渲染(source / entity / concept / analysis / comparison / synthesis)统一走
    `renderTagsLineSuffix(fm, {showTags})` 共用函数(对齐 #31)。
  - v0.6.5 (P0 issue #5): 删除硬编码占位 wikilink(Karpathy / ISO 26262 / S32G / S32K3 / LayerZero /
    Wormhole / 分析页 / 综合页 等),改为「*(暂无)*」骨架。aggregate-index.js 在 init 后会被用户
    触发,真实数据写入。
    之前:init 后用户工程 knowledge/index.md 末尾被追加真数据,前面占位保留,造成「占位 + 真数据」并存误导。
    现在:init 模板即干净,aggregate-index 重新生成时被覆盖为「真数据」+ 「空组 → *(暂无)*」。
    同时:Entities / Concepts / Analyses / Comparisons / Syntheses 节的 ### Person/Method/...
    H3 占位也删除(由 renderIndex 按 type 动态生成,避免双重 H3)。
  - (issue #11): 动态区用一对 AGGREGATE 聚合标记(START / END 的 HTML 注释)包住,占位说明段移入
    标记内。aggregate-index.js 每次 ingest 只整体替换两个标记之间的内容;Overview / Maintenance 是
    手写区(标记之外),脚本永不覆盖,项目简介等手写内容必须写在标记之外。
-->
# 项目名 Wiki 主目录

> **plugin 版本**:0.6.7
> **最近更新**:2026-09-04T10:30:00Z
> **自动生成**:本文件由 `/aeps-llm-wiki-init` 与 `/aeps-llm-wiki-ingest` 维护,不要手工编辑。
>
> 本文件无 frontmatter(OKF §3.1 reserved filename);本文件即 OKF §8 规定的 index.md。

---

## Overview

【一句话总览本项目 wiki 主题。手写区:本节在聚合标记之外,`scripts/aggregate-index.js` 不会覆盖;LLM 初始化时填写后长期保留。】

参见 [overview](./overview.md) 查看大图。

---

<!-- AGGREGATE-START -->
(动态区说明:两个聚合标记之间的全部内容由 `scripts/aggregate-index.js` 在每次 ingest 后整体重写;以下占位节首次聚合后被真数据替换,手工内容请勿写在这里。)

## Sources({数量})

【按 frontmatter `resource` 路径解析的 `raw/{subdir}/` 分组输出;子目录名去掉 `\d+_` 编号前缀。每条用 `[[wikilink|alias]]` 裸文件名 + title 别名格式,行结构 = `[[wikilink|alias]] —— description [status]`(默认);行尾 tags 默认不渲染(从 frontmatter.tags 读,不在 list 行展示);启用 `--show-tags` 时输出灰色 `<span style="color:gray">#tag</span>` 包装(对齐 #28)。无法解析 resource 路径的 source 归到 `### 其他`。LLM / 脚本生成,详见 `scripts/aggregate-index.js`。】

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
<!-- AGGREGATE-END -->

---

## Maintenance

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 子类判定示例 + 命名飘检查规则:`../doc/design/design.md §4.4`(待写)
- 本文件由 SKILL.md 在每次 ingest / query 落档 / lint --fix 时增量更新,**不要手工编辑**
- 聚合标记之外的 Overview / 本节是手写区;两个聚合标记之间由 `scripts/aggregate-index.js` 整体重写
