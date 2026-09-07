# 项目名 Wiki 术语表

> **plugin 版本**:0.5.2
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

## A

- **AGI**(Artificial General Intelligence,通用人工智能):具备与人类相当或超越的广泛认知能力的人工智能系统。相关:[[llm-wiki]]。
- **ASIL**(Automotive Safety Integrity Level,汽车安全完整性等级):ISO 26262 定义的危险事件风险分类等级(QM / A / B / C / D)。相关:[[iso-26262]]、[[hardware-architecture-metric]]。
- **AUTOSAR**(AUTomotive Open System ARchitecture):汽车开放系统架构标准,定义 CP(经典平台)/ AP(自适应平台)两套软件架构。相关:[[autosar]]。

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

- **LLM**(Large Language Model,大语言模型):基于 Transformer 架构的大规模语言模型。相关:[[llm-wiki]]。

## M

- *(暂无)*

## N

- *(暂无)*

## O

- **OKF**(Open Knowledge Format):Google Cloud 主导的开放知识格式,本 wiki 严格兼容 v0.2。相关:[[okf-v0-2]]。

## P

- *(暂无)*

## Q

- *(暂无)*

## R

- *(暂无)*

## S

- **synthesis**(综合页):`type: synthesis` 常驻综合页,由 `/aeps-llm-wiki-synthesize` 显式触发;整合 wiki 内 ≥3 个相关概念。

## T

- **TVL**(Total Value Locked,总锁仓价值):DeFi 协议中锁定的资产总价值。相关:[[cross-chain-bridge]]。

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

---

## 维护

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 本文件由 SKILL.md 在 `/aeps-llm-wiki-ingest` 检测到新术语时增量更新(LLM 提议 + 用户拍板)
