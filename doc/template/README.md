# aeps-llm-wiki-plugin —— Frontmatter Template 总览

本目录是 plugin 的 frontmatter **唯一权威模板来源**。init 时拷贝到用户项目的 `{project}/templates/`,SKILL.md 生成页时读对应 `page-{type}.md`。

> **权威顺序**:OKF v0.2 > **`doc/schema/frontmatter-spec.md`(人读字段规范,唯一权威)** > `doc/schema/frontmatter.schema.json`(机器读,跟随 spec) > `README.md`(本目录人读入口,总览) > `doc/schema/schema.md`(工作流入口)
>
> **对齐原则**:本目录所有 page-*.md 模板的字段定义以 `frontmatter-spec.md` 为最终裁决;若本目录模板与 spec 冲突,以 spec 为准。

---

## 1. 字段总表

### 1.1 OKF v0.2 原生字段(OKF reader 必须能消费)

| 字段 | OKF 章节 | 类型 | OKF 必填 | plugin 必填 | 用途 |
|---|---|---|---|---|---|
| `type` | §4.1 | string | **✅ 唯一硬必填** | ✅ 7 种取值 | OKF 唯一硬必填;plugin 取值见 §2 |
| `id` | §4.1 | string | OKF 推荐 | 选 | 稳定主键;plugin 默认用页面相对路径 |
| `title` | §4.1 | string | OKF 推荐 | ✅ 推荐 | Obsidian 顶部、index.md 第一列 |
| `description` | §4.1 | string | OKF 推荐 | ✅ 推荐 | 一句话总结;index.md 第二列 |
| `tags` | §4.1 | string[](6 轴前缀) | 选 | ✅ 推荐(plugin 强化为 6 轴字典约束) | Obsidian tag 面板 + plugin 第 1 跳关键词过滤;**每条 tag 必须以 `domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/` 之一为前缀**,详见 [`doc/template/tag-spec.md`](tag-spec.md) 6 轴字典 |
| `resource` | §4.1 | URI | 单源必填,多源不填 | 单源必填,多源不填 | 物理资源 URI。plugin 收紧:单源模式(`type: source`)顶层必填;多源融合模式(analysis/synthesis/comparison)改用 `sources[]`,顶层 `resource` 不填。详见 `frontmatter-spec.md` §4.2.3 |
| `sources` | §5.1 | list | 选 | source 必填 | `[{id, resource, title, author, last_modified, usage_count, ...}]` |
| `generated` | §5.2 | object | OKF 内部必填 | ✅ 推荐 | `{ by: agent:{name}, at: ISO8601 }` |
| `verified` | §5.2 | list | 选 | 选 | 人工确认;用户拍板可写入 |
| `status` | §5.4 | enum | 选 | 选 | `draft` / `stable` / `deprecated`;默认 `stable` |
| `stale_after` | §5.5 | ISO 8601 | 选 | 选 | 陈旧度唯一信号;`now >= stale_after` 即陈旧;**未填则静默跳过,不判陈旧** |

### 1.2 Plugin 扩展字段(OKF reader 按未知字段忽略,MUST NOT reject, MUST preserve on round-trip;OKF §4.1 + §11)

| 字段 | 类型 | plugin 必填 | 用途 |
|---|---|---|---|
| `source_file` | wikilink 文本 | source 必填 | Obsidian wikilink 文本,指向 raw/ 原文件;Obsidian 渲染为蓝色下划线可点击链接,跨 reader 降级显示原始文本。例:`[[06-功能安全/iso26262.pdf]]`。详见 `frontmatter-spec.md` §12.5 |
| `format` | string | source 必填 | 原文件扩展名(小写):`pdf` / `pptx` / `docx` / `png` ... |
| `converter` | string\|null | source 必填 | 实际走过的转换器:`anydoc` / `paddleocr` / `claude-native` / `null`(纯文本) |
| `native_text` | bool | source 必填 | 是否原生纯文本;决定是否生成 `.converted.md` |
| `converted_path` | path\|null | source 必填 | `.converted.md` 副本路径(程序消费);纯文本为 `null`。与 `source_file` 分工,详见 `frontmatter-spec.md` §12.5 |
| `sources_used` | string[] | analysis 必填 | 本次 query 参考的 wiki 页相对路径列表;lint C15.2 验存在 |
| `answer_to` | string | analysis 必填 | 原 query 问句;G11 落档分析页必备 |
| `sources_count` | int | analysis / synthesis / comparison 必填,其他 type 推荐 | 当前页引用的 wiki 页/资料数(入度);lint 判 synthesis 成熟度(< 3 WARN)。语义与 OKF §5.1 `sources[].usage_count`(原始素材被消费次数)不同 |
| `updated` | ISO 8601 | plugin 推荐 | LLM 最后一次综合推演该页的时间(读事件);lint C15.2 `--fix` 不动(Q7 死循环防护)。不参与陈旧度判断 |
| `summary` | string | analysis / synthesis / comparison 必填,其他 type 推荐 | 长摘要(≤ 280 字);Obsidian 顶部 summary 卡片。语义与 OKF `description`(单句静态摘要)不同:description 是定义,summary 是当前快照。详见 `frontmatter-spec.md` §12.3 |
| `aliases` | string[] | plugin 推荐 | Obsidian 原生别名机制,为页面注册若干别名,使 `[[alias]]` 形式的 wikilink 可解析到本页。详见 `doc/schema/schema.md` §3 + `frontmatter-spec.md` §12.4。OKF reader 按未知字段忽略(MUST NOT reject) |

> **命名约定**:plugin 扩展字段不加 `x-aeps-llm-wiki-` 前缀。OKF reader 按未知字段忽略即可,无需前缀声明。

### 1.3 Plugin **不发明** 的字段

| 字段 | 状态 | 原因 |
|---|---|---|
| `links:`(frontmatter) | ❌ 不发明 | OKF §5「Lineage is expressed through links, not a dedicated field」;链接全部走正文 |
| `[[wikilink]]`(正文) | ✅ 主推 | PRD §10 Q9 决策;Q6 决策 A 已废。裸文件名,依赖 Obsidian 唯一名解析;OKF §6.1 用词 "MAY standard markdown link"(允许而非禁止),wikilink 不与之冲突。lint C15.5 反转后不再 FAIL on wikilink 残留 |
| 标准 markdown 链接 | ✅ 兼容降级 | OKF §6.1 推荐;plugin 仍可识别 |

---

## 2. `type` 字段取值清单

### 2.1 entity(具象存在)—— 7 子类

- `entity.person` / `entity.organization` / `entity.project` / `entity.product` / `entity.event` / `entity.place` / `entity.other`

### 2.2 concept(抽象知识)—— 7 子类

- `concept.theory` / `concept.method` / `concept.field` / `concept.phenomenon` / `concept.standard` / `concept.term` / `concept.other`

### 2.3 其他

- `source`(源页)
- `analysis`(LLM 综合推演一次性快照)
- `comparison`(常驻对照页)
- `synthesis`(常驻综合页)

### 2.4 子类 ↔ 目录 1:1 绑死

| type 取值 | 知识库目录 |
|---|---|
| `entity.person` | `knowledge/entities/person/` |
| `entity.organization` | `knowledge/entities/organization/` |
| `entity.project` | `knowledge/entities/project/` |
| `entity.product` | `knowledge/entities/product/` |
| `entity.event` | `knowledge/entities/event/` |
| `entity.place` | `knowledge/entities/place/` |
| `entity.other` | `knowledge/entities/other/` |
| `concept.theory` | `knowledge/concepts/theory/` |
| `concept.method` | `knowledge/concepts/method/` |
| `concept.field` | `knowledge/concepts/field/` |
| `concept.phenomenon` | `knowledge/concepts/phenomenon/` |
| `concept.standard` | `knowledge/concepts/standard/` |
| `concept.term` | `knowledge/concepts/term/` |
| `concept.other` | `knowledge/concepts/other/` |
| `source` | `knowledge/sources/` |
| `analysis` | `knowledge/analyses/` |
| `comparison` | `knowledge/comparisons/` |
| `synthesis` | `knowledge/syntheses/` |

合计 **1 + 7 + 7 + 1 + 1 + 1 = 18 个值**。**权威 enum 清单见 [`doc/schema/frontmatter-spec.md` §4.1.1](../schema/frontmatter-spec.md)**(plugin 收敛 OKF §4.1 开放类型,只接受这 18 项)。

---

## 3. 文件清单

| 文件 | 用途 | OKF 兼容 |
|---|---|---|
| `README.md` | 本文件,字段总表 + 使用指南 | N/A |
| `frontmatter.schema.json` | 已迁至 `doc/schema/frontmatter.schema.json` | ✅ |
| `page-source.md` | `type: source`(4 路径分流:纯文本 / claude-native / anydoc / paddleocr;SKILL.md 按扩展名填 converter) | ✅ |
| `page-entity-person.md` | `type: entity.person`(7 子类共用骨架) | ✅ |
| `page-concept-theory.md` | `type: concept.theory`(7 子类共用骨架) | ✅ |
| `page-analysis.md` | `type: analysis`(query 落档,G11 专属骨架) | ✅ |
| `page-comparison.md` | `type: comparison`(常驻对照页) | ✅ |
| `page-synthesis.md` | `type: synthesis`(常驻综合页) | ✅ |
| `doc/schema/schema.md` | `doc/schema/schema.md`(Agent 操作手册,统一入口) | N/A(无 frontmatter) |
| `page-index.md` | `knowledge/index.md`(主目录) | N/A(无 frontmatter,OKF §8) |
| `page-overview.md` | `knowledge/overview.md`(大图) | N/A |
| `page-glossary.md` | `knowledge/glossary.md`(术语表) | N/A |
| `page-log.md` | `knowledge/log.md`(变更日志,OKF §9) | N/A |

---

## 4. 引用约定

- **正文链接一律用标准 markdown 链接**,形式 `[文本](./相对路径.md)` 或 bundle-relative `[文本](/相对路径.md)`(OKF §6.1)
- **Obsidian 原生支持跳转与反向链接面板**,无需 `[[wikilink]]`

---

## 5. lint 规则

| 规则 | 适用类型 | 行为 |
|---|---|---|
| 3 节骨架硬约束 | `source` / `analysis` | 必含 `## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`(source)或 `## 方案推演 / 架构分析` / `## 关联溯源` / `## 总结:最有收获的一句话`(analysis);缺一 FAIL |
| 禁用 `## 摘要` / `## Summary` | 所有 type | 长摘要走 frontmatter `summary` 字段;FAIL on 残留 |
| `comparison` 必填 `sources` | `comparison` | FAIL on 缺失 |
| `synthesis` `sources_count` < 3 | `synthesis` | WARN(避免空综合) |
| `analysis` 必填 `sources_used` | `analysis` | 每条路径必须解析到真实存在的 `knowledge/**/*.md`;否则 FAIL |
| `analysis` `## 关联溯源` 末行 `> 引用:` 与 `sources_used` 一致 | `analysis` | lint Set 比对,不一致 WARN |
| `[[wikilink]]` 与标准 markdown 链接混用 | 所有 type | 同段落二选一,优先 wikilink(Q9 决策);`--fix` 自动转 wikilink(待实现) |
| `links:` frontmatter 字段残留 | 所有 type | FAIL;`--fix` 删除字段(对齐 OKF §5) |

---

## 6. 使用指南

本节回答一个根本问题:**这些模板文件怎么被 plugin 用?**

### 6.1 两类文件,不同用途

| 类别 | 文件 | 作用 | 谁读 |
|---|---|---|---|
| **页面模板** | `page-{type}.md`(9 个:`source` / `entity-{person,organization,...}` / `concept-{theory,method,...}` / `analysis` / `comparison` / `synthesis` / `index` / `overview` / `glossary` / `log`) | 告诉 LLM "生成一个这种 `type` 的页面时,frontmatter 长啥样 + 正文骨架是啥" | 每个 skill 的 SKILL.md |
| **字典规范** | `tag-spec.md` / `rawdir-spec.md` / `concept-entities-spec.md` | LLM 填字段时**查表**:tags 取值不能瞎写,子目录命名要按字典拍,entity/concept 二选一要按判定规则 | SKILL.md 跑时作为"约束输入"注入 LLM prompt |

> **注意**:字段定义的**唯一权威**是 `doc/schema/frontmatter-spec.md`(本 README 第 0 段"权威顺序"已写);本目录**不是字段定义**,是"字段 + 骨架 + 例子 + 维护说明"的打包体。模板与 spec 冲突时以 spec 为准。

### 6.2 数据流

```
                          ┌─────────────────────────────────────────┐
                          │ doc/template/ (本目录,plugin 仓库内)     │
                          │ 唯一权威模板源                            │
                          └────────────┬────────────────────────────┘
                                       │ init 阶段整目录拷贝
                                       ▼
                          ┌─────────────────────────────────────────┐
                          │ {user-project}/templates/                │
                          │  用户工程内的工作副本                      │
                          └────────────┬────────────────────────────┘
                                       │ SKILL.md 读
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
       page-{type}.md          tag-spec.md           rawdir-spec.md
       (生成页面骨架)         (6 轴 tag 约束)            (15 类子目录字典)
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       ▼
                          SKILL.md 替换变量 + 查表
                                       │
                                       ▼
                          ┌─────────────────────────────────────────┐
                          │ {user-project}/knowledge/                │
                          │  sources/ entities/ concepts/ analyses/  │
                          │  comparisons/ syntheses/                 │
                          │  index.md overview.md glossary.md log.md │
                          └─────────────────────────────────────────┘
```

### 6.3 init 阶段:整目录拷贝 + 不覆盖

按 PRD §4.1,init skill 跑时:

1. **整目录拷贝** `doc/template/` → `{user-project}/templates/`
2. **同时拷贝** `doc/schema/` → `{user-project}/schema/`
3. SKILL.md 在用户工程内**优先读本地** `templates/page-{type}.md`,plugin 仓库仅作 fallback

**关键纪律**:`{user-project}/templates/` 不是死文件。re-run init 时**不覆盖已有模板**(PRD §4.1 同步策略表写明),只补建缺失模板。这是为了让用户可以在自己工程里改模板而不被 plugin 升级冲掉。

### 6.4 运行时:5 个 skill 各自的读写关系

| Skill | 读哪些模板 | 写哪类页面 |
|---|---|---|
| **init** | 全部模板(9 个 `page-*.md` + 3 个字典) | `index.md` / `overview.md` / `glossary.md` / `log.md`(从对应模板建空白) |
| **ingest** | `page-source.md`(按 5 路径分流填变量)+ `page-entity-{subtype}.md` / `page-concept-{subtype}.md`(按 LLM 提议的 entity/concept)+ `tag-spec.md` + `rawdir-spec.md` + `concept-entities-spec.md` | `knowledge/sources/{slug}.md` + `knowledge/entities/{subtype}/{slug}.md` + `knowledge/concepts/{subtype}/{slug}.md` + 增量更新 `index.md` / `glossary.md` / `log.md` |
| **query** | `page-analysis.md`(G11 M1 落档,3 节专属骨架) | `knowledge/analyses/{timestamp}-{slug}.md` |
| **synthesize** | `page-synthesis.md`(常驻综合页)+ `tag-spec.md`(tags 6 轴) | `knowledge/syntheses/{topic-slug}.md` |
| **lint** | **不写页**,只校验现存的页 frontmatter 是否符合 `schema/frontmatter-spec.md`;模板作为"预期形态"对照(例如 analysis 页必含 `## 关联溯源`) | — |

### 6.5 几个易混点

- **`page-source.md` 是 9 个模板里最厚的**(约 158 行),因为它内嵌了"5 路径分流表 + 完整 frontmatter 例子"。它是 SKILL.md 在 ingest 时**唯一需要查表**的模板;其他模板 LLM 拿到就能直接生成。
- **`page-index.md` 没有 frontmatter**(OKF §3.1 reserved filename) —— 它是 OKF §8 规定的特殊文件,plugin 不把 `type` 字段塞进去。同样,`page-overview.md` / `page-glossary.md` / `page-log.md` 也无 frontmatter。
- **5 路径分流 ≠ 路径 4 OCR 单选**:`page-source.md` 里的分流表把 `.ppt/.doc/.xls` 老格式放在"路径 3 失败回退"位(PRD §4.2 路径 0 自由化,详见 PRD),实际跑 ingest 时 SKILL.md 会先走 LibreOffice 预归一化,再走路径 3。模板分流表与 PRD 同步以 PRD 为准。
- **6 轴 tag 在哪里查**:生成任何新页时,SKILL.md 把 `tag-spec.md` 注入 LLM prompt 作为受控词表;LLM 选 tag 必须从 6 轴内选,不允许自创未在前缀列表(`domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/`)下的新前缀。
- **`concept-entities-spec.md` 的判定时机**:每次 ingest 时 SKILL.md 让 LLM 判定"这个抽取出的实体是 entity 还是 concept、是哪个子类"前,**必须**先读这个规范;不允许凭直觉选 7 子类之一。

### 6.6 修改模板的纪律

- **字段定义变更**:改 `doc/schema/frontmatter-spec.md`(人读权威),同步 `doc/schema/frontmatter.schema.json`(机器读);模板里改了不算数(权威顺序已固定)。
- **骨架/例子变更**:改本目录对应 `page-{type}.md`;re-run init 时不覆盖用户本地副本,需用户手工同步。
- **字典规范变更**:改 `tag-spec.md` / `rawdir-spec.md` / `concept-entities-spec.md`;同样 re-run init 不覆盖用户本地副本。
- **plugin 升级时**:同步发布一份 `doc/template/CHANGELOG.md` 说明本次升级模板变更点,init skill re-run 不会自动应用,用户需手动 diff。