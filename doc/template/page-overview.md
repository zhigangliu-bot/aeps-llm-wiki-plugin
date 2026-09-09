<!-- 提示:本页是 plugin 自定义 reserved filename,无 frontmatter;若本批次未来加上 frontmatter,tags 示例务必 ≥ 6 条,避免 LLM 按 5 条填导致 WARN。详见 P3-4 修复。 -->
# 项目名 Wiki 大图

> **plugin 版本**:0.6.4
> **最近更新**:2026-09-04T10:30:00Z
>
> 本文件无 frontmatter(本文件是 plugin 自定义 reserved filename,不在 OKF §3.1 列表内);由 `/aeps-llm-wiki-ingest` 在"大图变化时"更新。

---

## 一句话定位

【本项目 wiki 主题的一句话定位。】

---

## 主题领域分布

【按 `tags` 聚合,LLM 自动生成。例:】

- **功能安全**({数量} 页):[ISO 26262](./concepts/standard/iso-26262.md)、[ASIL](./concepts/term/asil.md)、[硬件架构度量](./concepts/method/hardware-architecture-metric.md)、[软件单元测试](./concepts/method/software-unit-testing.md)
- **AI 与 LLM**({数量} 页):[LLM Wiki 模式](./concepts/theory/llm-wiki.md)、[OKF v0.2](./concepts/standard/okf-v0.2.md)、[Karpathy](./entities/person/andrej-karpathy.md)
- **汽车电子**({数量} 页):[AUTOSAR](./concepts/standard/autosar.md)、[S32G](./entities/product/s32g.md)、[S32K3](./entities/product/s32k3.md)
- **区块链**({数量} 页):[跨链桥概念](./concepts/theory/cross-chain-bridge.md)、[LayerZero](./entities/product/layerzero.md)、[Wormhole](./entities/product/wormhole.md)

---

## 知识成熟度

【按 `synthesis` / `comparison` / `analysis` 数量 + `sources_count` 评估,LLM 自动生成。】

- **成熟综合**({数量}):[汽车功能安全体系综合](./syntheses/automotive-functional-safety.md)(sources_count=5)
- **常驻对照**({数量}):[LayerZero vs Wormhole 跨链机制对比](./comparisons/layerzero-vs-wormhole.md)
- **近期推演**({数量}):见 [analyses 目录](./analyses/)

---

## 未覆盖领域

【按用户近期 query 但 wiki 未覆盖的领域,LLM 自动生成。】

- *(LLM 自动从 log.md query 记录 + 当前 knowledge/ 缺口推断)*

---

## 维护

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 本文件由 SKILL.md 在"大图变化时"更新(新增 source / 完成 synthesis / 累计 analyses > 10 等触发条件)
