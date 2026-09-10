<!-- 提示:本页是 plugin 自定义 reserved filename,无 frontmatter;若本批次未来加上 frontmatter,tags 示例务必 ≥ 6 条,避免 LLM 按 5 条填导致 WARN。详见 P3-4 修复。 -->

<!-- change history:
  - v0.6.5 (P0 issue #5): 删除硬编码占位术语(AGI / ASIL / AUTOSAR / LLM / OKF / synthesis / TVL 等),
    所有 26 个字母段改为「*(暂无)*」骨架。aggregate-index.js 重新生成时按 wiki 内真实 title + aliases
    写入;无任何 wikilink 指向不存在的占位术语页(原 llm-wiki / iso-26262 / hardware-architecture-metric /
    autosar / okf-v0-2 / cross-chain-bridge 等 wikilink 已删除,因 init 时这些页根本不存在)。
  - (issue #11): A-Z 动态区用一对聚合标记(START / END 的 HTML 注释)包住;aggregate-index.js 每次
    ingest 只整体替换两个标记之间的内容。「使用说明」与「维护」是手写区(标记之外),脚本永不覆盖;
    LLM / 用户手工术语条目必须写在标记之外。
-->
# 项目名 Wiki 术语表

> **plugin 版本**:0.6.6
> **最近更新**:2026-09-04T10:30:00Z
>
> 本文件无 frontmatter(本文件是 plugin 自定义 reserved filename,不在 OKF §3.1 列表内);由 `/aeps-llm-wiki-init` 创建 + `/aeps-llm-wiki-ingest` 增量更新。

---

## 使用说明

- **plugin 术语**(`OKF` / `KARMA` / `WIKI` 等 plugin 自定义概念):走"plugin 词典"append 策略,见 PRD §4.1 幂等再入
- **领域术语**(`ASIL` / `AUTOSAR` / `TVL` 等)按字母序排列,每条带一句话定义 + 至少 1 个相关 wiki 页 `[[wikilink]]`(裸文件名,主推;PRD §10 Q9)
- **词典 sync**(init / re-init 时):
  - 用户项目里**没有** → 直接复制
  - **新增章节/条目** → append 到对应 H2 末尾
  - **用户已删** → 不补回,lint 提示"plugin 新版有 X 条本地无,要不要采纳?"

---

<!-- AGGREGATE-START -->
(动态区说明:两个聚合标记之间的全部内容由 `scripts/aggregate-index.js` 按 wiki 内真实 title + aliases 整体重写;手工术语条目请写在标记之外。)

## A

- *(暂无)*

## B

- *(暂无)*

## C

- *(暂无)*

## D

- *(暂无)*

## E

- *(暂无)*

## F

- *(暂无)*

## G

- *(暂无)*

## H

- *(暂无)*

## I

- *(暂无)*

## J

- *(暂无)*

## K

- *(暂无)*

## L

- *(暂无)*

## M

- *(暂无)*

## N

- *(暂无)*

## O

- *(暂无)*

## P

- *(暂无)*

## Q

- *(暂无)*

## R

- *(暂无)*

## S

- *(暂无)*

## T

- *(暂无)*

## U

- *(暂无)*

## V

- *(暂无)*

## W

- *(暂无)*

## X

- *(暂无)*

## Y

- *(暂无)*

## Z

- *(暂无)*
<!-- AGGREGATE-END -->

---

## 维护

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 本文件由 SKILL.md 在 `/aeps-llm-wiki-ingest` 检测到新术语时增量更新(LLM 提议 + 用户拍板)
- 两个聚合标记之间由 `scripts/aggregate-index.js` 整体重写;手工条目写在标记之外
