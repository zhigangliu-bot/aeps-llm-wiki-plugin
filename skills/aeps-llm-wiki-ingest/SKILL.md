---
name: aeps-llm-wiki-ingest
description: 把用户丢进 inbox/ 的资料按 5 路径分流归档到 raw/ 与 knowledge/,含双向反链与 log 更新
plugin-version: 0.6.6
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/preflight.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/classify.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/convert-to-md.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/init-batch.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/move-to-raw.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/build-related-pages.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/append-log.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/lint-stub.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(ls temp/ingest-batch-*.json*),Bash(rm temp/ingest-batch-*)
---

> **change history**(本文件 v0.6.x 起每次变更追加一行):
> - **v0.6.6 (PR-B)** — 步骤 14 / 15 同步 PR-B 渲染约定:glossary 按术语首字母分组输出 ## A / ## B / ... 节(中文术语归 ## 中文;空字母节省略);index.md 行尾 tags 默认不渲染(`<span style="color:gray">#tag</span>` 省略,避免灰底冲淡 description,#28),启用 `--show-tags` CLI 开关时恢复旧行为(#31 兼容);LLM 不再手工删除行尾 tags(由脚本统一控制)。
> - **v0.6.6 (PR-C)** — 步骤 3 提示 LLM 在 batch.files[] 写 `entities[]` / `concepts[]`(对齐 build-related-pages.js:697-700 schema),append-log 据此追加;步骤 4 新增路径字段名 alias 提示(`source_path` / `file_path` / `file` → `path` 归一,init-batch `normalizeFileEntry` 实现,修复 issue #25);步骤 11 引用 lint-stub **R7.4** 字典前缀校验(修复 issue #21);步骤 17 追加 entity/concept 抽取列自动写入 log.md(修复 issue #30)。

## 脚本路径约定

> **脚本路径约定**:本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin-root;该变量由调用方注入(plugin 自动注入或用户 shell 导出),或通过 `--plugin-root` CLI 参数显式传递冗余兜底。

- 脚本均在 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- 默认调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT} ...`(env 已注入)
- 兜底调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --plugin-root ${CLAUDE_PLUGIN_ROOT} ...`(env 注入失败时显式冗余)
- `build-related-pages.js` 还支持 `--schema-path <absolute>` 显式覆盖 schema 路径;支持 `--project <绝对路径>` 显式指定用户工程根。
- `gen-page.js` 还支持 `--project <绝对路径>` 显式指定用户工程根(模板路径解析用)。
- 当 `${CLAUDE_PLUGIN_ROOT}` env 未注入(plugin loader 未生效 / shell 没 export),`--plugin-root` 是唯一兜底,**必须**显式传。

# /aeps-llm-wiki-ingest

把用户资料从 `inbox/` 迁移到 `raw/{subdir}/`,生成 `knowledge/sources/<slug>.md` 源页,抽取 entity / concept 子页,双向反链,更新 `index.md` / `log.md` / `overview.md` / `glossary.md`。

## 触发

用户在 `inbox/` 丢资料后跑 `/aeps-llm-wiki-ingest`(无参数,递归扫 `inbox/`)。

## 路径布局(plugin 仓 vs 用户工程)

plugin 仓根目录与 sync-files 同步出的用户工程根目录布局不同,这是 sync-files.js 故意分开的两个命名空间,**不是 bug**;脚本运行时用 `import.meta.dirname` 解析 plugin 仓路径,不依赖 cwd。

| plugin 仓根 | 用户工程根 | sync 行为(sync-files.js) |
|---|---|---|
| `doc/schema/` | `doc/schema/` | overwrite(SYNC-6) |
| `doc/template/` | `doc/templates/`(复数,可接受差异) | backfill missing;preserve existing |
| `scripts/` | `scripts/` | backfill missing;preserve existing |
| `.claude-plugin/` | — | 不进用户工程(由 plugin loader 处理) |

## 设计原则(必读)

- **原生多模态优先**(PRD G10 + design §3.2):Claude Code 原生能读 → 路径 1/2 直接结束,**不生成 .converted.md**,不调 `convert-to-md.js`;不能 → 路径 3/4。
- **不重转**(PRD G10 + §7.1):raw/ 不可变;需重转时由用户 `cp` 回 inbox/ 重跑。
- **拍板门强制**:raw/ 子目录分类 / 已存在同名 / 命名飘 → 必须用户拍板,脚本不静默决定。
- **batch.json 状态总线**:本次 ingest 所有文件状态共享 `temp/ingest-batch-{ts}.json`,后续脚本顺序读。
- **JSON stdout**:所有 ingest 脚本输出结构化 JSON 到 stdout,SKILL.md 用 `JSON.parse` 解析。

## 编排流程(SKILL.md 只编排,不写实现)

按 PRD §4.2 流程表 19 步执行;每步标注 LLM / 脚本 / 拍板门。

### 步骤 0:探查原生能力 + 残留 batch

```bash
# 0.1 检测 temp/ingest-batch-*.json 残留
ls temp/ingest-batch-*.json 2>/dev/null
```

- 有残留 → 询问用户:`[清理] / [继续上次] / [失败回滚]`
- 无 → 继续

对 inbox 每个文件,先让 Claude Code 直接读;能读 → 路径 1/2;不能 → 路径 3/4。

### 步骤 0.5:依赖 preflight(可选)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/preflight.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --scripts-dir <用户工程根>/scripts --json
```

读 stdout JSON:

- `ok == true` → 进入步骤 1
- `ok == false` → 缺失依赖,按 stderr `npm install` 提示让用户装,exit 0 后重跑本步

### 步骤 1:扫 inbox

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --inbox inbox/ --json
```

读 stdout JSON:
- `count == 0` → 提示"inbox 为空",exit 0
- `count > 0` → 进入步骤 2

### 步骤 2:5 路径分流

```bash
# 对每个文件分别调(也可用 --batch 批模式)
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/classify.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --file inbox/<file> --check-deps --json
```

读 stdout JSON:
- `route == 1` → 纯文本,**不调** `convert-to-md.js`
- `route == 2` → PDF 原生可读,**不调** `convert-to-md.js`
- `route == 3` → 调 `convert-to-md.js`(PDF/HTML 走 anydoc;docx/pptx/xlsx 走 docling)
- `route == 4` → 调 `convert-to-md.js`(paddleocr);若 classify.js 返回 `fail: true` → 路径 4 不可用,询问用户装 paddleocr,**FAIL 不降级**(G6 + implement-ingest.md §1.1)
- PDF 原生失败 → 用 `--route 3` 覆盖默认(SKILL.md 显式重跑)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/convert-to-md.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --file inbox/foo.pdf --emit-to inbox/ --json
```

- 路径 1/2 → 跳过本步
- 路径 3/4 → 必调;转换副本落 `inbox/<basename>.<ext>.converted.md`(与原文件同目录,move-to-raw 时一起迁)

### 步骤 3:raw 子目录 + 命名飘拍板门

LLM 读取每个文件(原文件或 `.converted.md`),提议:
- `target_subdir` ∈ 15 raw 子目录字典(`doc/template/rawdir-spec.md`);**`subdir` 与 `target_subdir` 等价,均可接受**(init-batch.js 会归一为 `target_subdir`,两者同时存在时显式 `target_subdir` 优先)
- 每抽 entity / concept 提议 slug(对齐 `concept-entities-spec.md` 14 子类判定),并**在 batch.files[] 提供 `entities[]` / `concepts[]` 数组,每项 `{type, slug, title?}`**(对齐 build-related-pages.js:697-700 schema;append-log 据此在 **Ingest** 行尾追加 entity/concept 抽取列,v0.6.6 PR-C #30)

命名飘检查:已有 wiki 页与新抽 entity slug Levenshtein ≤ 2 → WARN 提示强制改用。

SKILL.md 与用户对话拍板,**不**写 `infer-intent.js` / `dedupe.js`(LLM 决策,SKILL.md 管)。

### 步骤 4:创建 batch + 迁 raw/

```bash
# 文件少(≤10 条)→ 内联 JSON 字符串
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/init-batch.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> \
  --files '<scan-inbox JSON 的 files[]>' \
  --emit-dir <用户工程根>/temp/ --json
```

```bash
# 文件多 / 路径含中文+空格 / 转义麻烦 → 落 temp/batch.json,走 --files-file
echo '[{...}, {...}]' > temp/batch.json    # ← 顶层就是数组,不是 {files: [...]}
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/init-batch.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> \
  --files-file <用户工程根>/temp/batch.json \
  --emit-dir <用户工程根>/temp/ --json
```

> `--files` 与 `--files-file` 互斥(二选一,都传/都不传 → ERROR exit 1)。

> ⚠️ `--files` / `--files-file` 的内容必须是**裸 JSON 数组**(`[{...}, {...}]`,即 scan-inbox JSON 的 `files` 字段取值本身)。**不能**包 `{files: [...]}` 外层——后者会被 init-batch.js 当输入数组处理,报 `inputFiles.map is not a function`。

> **PR-C (v0.6.6) 字段名 alias**:batch.files[] 的路径字段**权威名 = `path`**;LLM 写 `source_path` / `file_path` / `file` 也可接受,init-batch.js 内部 `normalizeFileEntry()` 归一为 `path`,优先级 `path > source_path > file_path > file`(修复 issue #25 v0.6.6 回归 bug)。同步支持:`ext` / `file_ext`、`subdir` / `target_subdir`、`slug` / `source_slug` 别名归一;`entities[]` / `concepts[]` 透传(供步骤 17 append-log 追加)。

读 stdout JSON `batch_file`,后续 3 步脚本都用此文件。

```bash
# dry-run 先看
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/move-to-raw.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --json

# 拍板后 --apply (若有同名冲突,先 --decision y|n|d)
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/move-to-raw.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --decision y --apply --json
```

- `[y]` 覆盖:先备份 `temp/raw_backup_{hash}/` + `os.replace()` 原子替换
- `[n]` 跳过:status=skipped,inbox 文件保留
- `[d]` 仅删旧副本
- 若 `batch.files[]` 提供 `slug` 字段,文件按 `{slug}.{ext}` 落地(原扩展名保留)。slug 已存在 → SKIP + WARN 不覆盖;slug 非法 → ERROR。

### 步骤 5:提取要点对话(可"继续"跳过)

防 spam 对话;LLM 解读产出,可让用户跳过。

### 步骤 6:建 source 页 skeleton

LLM 拍板下面 4 个 OKF 推荐字段后传入 `gen-page.js`(对齐 `templates/page-source.md` 模板头部,避免前次 M2.2 落地时的字段缺失 bug):

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --project <用户工程根> \
  --type source --slug <slug> \
  --ext <ext> --subdir <raw_subdir> \
  --title "<title>" \
  --description "<OKF v0.2 §4.1 推荐:一句话 30-80 字概括>" \
  --tags "docform/<...>,domain/<...>,maturity/<...>,tec/<...>" \
  --summary "<OKF v0.2 §4.1 推荐:50-150 字精要>" \
  --stale-after "<+1 年 ISO 8601>" \
  --source-file '[[<subdir>/<slug>.<ext>|<display>]]' --json
```

参数说明:

- `--description`:OKF v0.2 §4.1 推荐字段;`template/page-source.md` 已含示例。LLM 根据标题 + 文件名给一句话 30-80 字概括
- `--tags`:6 轴字典(`doc-spec.md`),必填 `docform/` + `domain/`,共 5-10 条
- `--summary`:OKF v0.2 §4.1 推荐字段;LLM 写完正文后回到 frontmatter 补,50-150 字
- `--stale-after`:默认 `generated.at + 1 年`(ISO 8601);LLM 可根据资料类型调整(标准/规范 → 5 年;时事 → 6 月)
- `--source-file`:Obsidian wikilink,`[[<subdir>/<slug>.<ext>|<display>]]` 格式;`template/page-source.md` 示例参考

如果 4 个字段 SKILL.md 一时拿不准,**步骤 7 写完正文后回步骤 6 补传**重跑(`--out` 覆盖目标文件)。

### 步骤 7:LLM 填 source 正文

仅改 H2 之间正文;**不**改 frontmatter 字段值 / H2 顺序 / `## 维护说明` 尾巴(对齐 design §4.3 SKILL.md 硬约束)。

**强 prompt**:LLM 读完源文件后,**先**问自己:**这篇 source 有什么独特结构?** 在 `## 重点摘录` 之前用 1-N 个 H2 节呈现(占位骨架 `## 阅读路线` 强烈建议改名,如 `## 来源元信息` / `## 核心要点` / `## 关键引用` / `## 适用范围` / `## 术语定义` / `## 关键约束` / `## 技术原理` / `## 性能指标` / `## 与同类对比` / `## 研究背景` / `## 方法` / `## 结果` / `## 结论` 等)。极短源文件可保留占位名 + 一句豁免说明。**所有自由追加节强制溯源**(lint C21 WARN)。

**正文书写顺序**:`# 标题` → **[自由追加节 1..N]** → `## 重点摘录` → `## 我的思考` → `## 总结:最有收获的一句话` → (脚本追加 `> 原始来源:` blockquote + Related Pages 占位)。

写完正文后,**回头把 `--summary` 字段值写入 frontmatter**;**不**重跑 `--out` 全量覆盖,改用 `--patch-frontmatter-only` 只 patch frontmatter;目标文件不存在 → fallback 全量生成(WARN stderr)。**v0.6.5 起 patch 模式全字段支持**(复用同一注入管道):`--tags` / `--description` / `--aliases` / `--summary` / `--title` / `--stale-after` / `--source-resource` / `--source-title` 均可 patch;CLI 未传的字段保留文件现有值,不会清空。

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --type source --slug <slug> --ext <ext> \
  --out <已存在的目标文件.md> \
  --patch-frontmatter-only \
  --summary "<补 50-150 字精要>" --title "<如有调整>" \
  --description "<如有调整>" --tags "docform/<...>,domain/<...>,..." \
  --aliases "<别名1>,<别名2>" --stale-after "<ISO 8601 datetime>" --json
```

> **PR-A (v0.6.6) 增量提示**:
>
> - **stdout JSON 契约**(修复 issue #19/#26):所有调用加 `--json`;SKILL.md 解析 stdout `JSON.parse(...)`。
>   关闭 `--json` 时保留旧 `OK: ...` / `HINT: ...` 文本(向后兼容老 LLM 客户端)。
> - **frontmatter 字符串字段保持双引号包裹**(修复 issue #23):LLM 在步骤 11-2 手工 Edit
>   frontmatter 时,所有字符串字段必须保留双引号(`title: "X"` 而非 `title: X`),否则下游
>   ajv schema / YAML 解析器可能把 `#` 注释行误当字段延续,触发 FAIL。
> - **patch 模式 stdout WARNING**(修复 issue #22/#26):stdout JSON 含
>   `generated_h2_sections[]`(脚本生成 H2 列表,如 `## 关联导引` / `## 来源资料` /
>   `## 相关页面(Related Pages)` / `## 维护说明`)+ `WARNING` 字段,告知 LLM:
>   重跑 `build-related-pages` 会**追加**而非重建。LLM 读 WARNING 后可选:
>   1. 加 `--strip-generated-h2` 一次性清掉 4 个脚本 H2,再 patch;
>   2. 手工 Edit 删除这些 H2 区块。
> - **stale_after 基准**(修复 issue #24):默认 `generated.at + TTL`;若显式传
>   `--stale-after-base updated`,改按 `updated + TTL` 重算(用于 patch 模式)。

来源不足自检:每条断言自检能否在源文件找到依据;无法溯源 → 显式标注 `[来源不足,需人工复核]`。

### 步骤 8:追加 `> 原始来源:` + Related Pages 占位

由 `gen-page.js` 自动在 `## 重点摘录` 顶部追加 `> 原始来源:` blockquote。Related Pages 占位由 build-related-pages.js(步骤 13)写。

### 步骤 9:判定 entity / concept 抽取

LLM 读 raw + `concept-entities-spec.md` 判 18 子类。

**踩坑对照表(v0.6.5,gen-page 传参前必查)**:

| 字段 | ✅ 正确写法 | ❌ 错误写法 | 后果 |
|---|---|---|---|
| `sources[]` | 对象列表 `sources:\n  - resource: "[[<source-slug>]]"\n    title: "来源页标题"`(gen-page 用 `--source-resource <slug> --source-title "<title>"` 注入) | 字符串列表 `- "[[xxx]]"` | build-related-pages 校验失败;反链失效 |
| `stale_after` | ISO 8601 **datetime** `"2027-09-09T00:00:00Z"`(带 `T…Z`;gen-page 缺省会自动按 `generated.at + 1 年` 推导,concept.standard +5 年) | 纯 date `"2027-09-09"` | schema/ lint FAIL,需改为 datetime |
| `tags` | **5-10 条**,必含 `docform/` + `domain/` 轴(字典:`doc/template/tag-spec.md`;gen-page 缺省按 type 子类注入 5 条,LLM 应精修) | 少于 5 条 / 裸 tag 无轴前缀 / 人名进 tag | lint FAIL/WARN;检索退化 |

> **PR-C (v0.6.6) lint-stub R7.4 字典前缀校验**:`scripts/ingest/lint-stub.js` v0.6.6 起新增 R7.4 校验 —— 每条 tag 必须匹配 `^(domain|layer|phase|docform|maturity|tec)/[a-z0-9][a-z0-9-]*$`(对齐 `doc/schema/frontmatter-spec.md §4.2.4` + `doc/template/tag-spec.md §1.4`);违规 → ERROR(fail++,exit 2)。同步新增:**必填轴** `docform/` + `domain/` 各 ≥1 条(tag-spec.md §1.2)、**单值轴** `docform/` + `maturity/` 不可重复(tag-spec.md §1.3)。`STUB_VERSION` M2.4-stub → M2.5-stub。修复 issue #21。

### 步骤 10:建 entity / concept 页 skeleton

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --project <用户工程根> \
  --type <entity|concept>.<subtype> --slug <slug> \
  --title "<title>" \
  --description "<一句话 30-80 字>" \
  --tags "docform/<...>,domain/<...>,layer/<...>,maturity/<...>,phase/<...>" \
  --source-resource "<source-slug>" --source-title "<source title>" \
  --aliases "<别名1>,<别名2>" \
  --summary "<50-150 字精要>" \
  --stale-after "<ISO 8601 datetime,如 2027-09-09T00:00:00Z>" \
  --json
```

- `--description` / `--tags` / `--aliases` / `--summary` / `--stale-after` / `--source-resource` / `--source-title` 均可省略:**CLI 传入 > 脚本自动推导 > 模板默认**。缺省时 gen-page 自动注入最小合规 skeleton(tags 按 type 子类从 6 轴字典注入 5 条;aliases fallback `[title]`;**v0.6.6 起 description/summary 不再静默 fallback 到 title,留空字符串 + stderr WARN**(issue #20);stale_after 自动 `generated.at + 1y`);`--source-resource` / `--source-title` 都不传 → `sources: []` 且 stdout 给出 `HINT: sources 为空` 提示,LLM 需在步骤 11 用 `--patch-frontmatter-only` 补。

**v0.6.5 起 `--project <用户工程根>` 必传**:`gen-page.js` 从 `<project>/doc/templates/` 找模板(issue #4-Bug3);
不传 → `template not found` 错误(对齐 PR-AC-6,v0.5.8 起取消 cwd 兜底)。
并发调用多个 `gen-page.js --json` 时也必须显式 `--project`,否则 `projectRoot` 解析失败。

**entity.* / concept.* 通用骨架**:`gen-page.js` 按 `entity.<subtype>` 自动选 [`page-entity.md`](../doc/template/page-entity.md);按 `concept.<subtype>` 自动选 [`page-concept.md`](../doc/template/page-concept.md)。子类差异通过 `type` 字段 / `aliases` / `tags` / 自由正文组织,**不**用 H2 节名体现。

> **PR-A (v0.6.6) 章节顺序约定**(issue #19):模板 `page-entity.md` / `page-concept.md` /
> `page-source.md` 默认章节顺序为**「实质内容在前,关联导引/来源资料/维护说明在后」**。
> LLM 在步骤 11 写正文时,把实质 H2 节(`## 个人背景` / `## 核心原理` / `## 适用范围` 等)
> 放在 `## 关联导引` **之前**;`## 关联导引` / `## 来源资料` / `## 维护说明` 由 plugin
> 脚本追加 / 维护,LLM 不必手工改这 3 节。

### 步骤 11:LLM 填 entity / concept 正文

自由发挥。`tags` / `aliases` / `description` / `summary` / `stale_after` 在 gen-page 阶段已注入最小合规 skeleton(步骤 10);`sources[]` 传了 `--source-resource` / `--source-title` 时已是对象格式,否则为空数组(stdout 有 HINT)—— **LLM 需补 source 时重跑 `--patch-frontmatter-only --source-resource <slug> --source-title "<title>"`**(patch 模式全字段支持,CLI 未传字段不会被清空)。若用户改 entity/concept 的 sources 引用,build-related-pages.js 步骤 12 会自动反向重建。

> **PR-A (v0.6.6) frontmatter 引号保持提示**(issue #23):LLM 在步骤 11-2 手工 Edit frontmatter 时,
> **所有字符串字段必须保留双引号包裹**(`title: "X"` 而非 `title: X`;`description: "d"` 同理)。
> 裸字符串会让下游 ajv schema / YAML 解析器把 `#` 注释行误当字段延续,触发 FAIL。
> gen-page 自动生成的 frontmatter 已保证双引号(由 `JSON.stringify`);LLM 修改时只动值不动引号。

### 步骤 12:回填 source 页 `## 相关页面` + entity/concept 页 `## 来源资料`(双向反链,**追加 + 保留**)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/build-related-pages.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 扫所有 source / entity / concept 页 frontmatter
- source 页 → 写 `## 相关页面(Related Pages)`(Entities / Concepts 分组)
- entity/concept 页 → 写 `## 来源资料`(按 source title 排序)
- 每次 ingest 在区块末尾追加新确认的反链(去重 wikilink 字符串);**保留** 区块下所有现有条目(含人工补的)。
- 同 wikilink 重复 → 保留人工条目(可能带更详细批注),stderr WARN `duplicate wikilink [[xxx]] 已在人工条目中存在,保留人工条目`。
- **若需完全重建**,先手工删除 `## 相关页面(Related Pages)` / `## 来源资料` 区块再跑脚本。
- 区块不存在 + 本次有反链 → 新建区块;区块不存在 + 本次无反链 → 文件不动(action=`*-unchanged`)。
- 某组空 → 省子标题;全空 → 省整节(仅当区块不存在时;区块已存在则保留人工条目)。

### 步骤 13:更新已有 wiki 页

LLM 决定:命名飘合并 / 改链等。

### 步骤 14:更新 glossary.md(aggregate-index,sentinel 区间重写)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --knowledge knowledge/ --json
# PR-B (issue #29):glossary 按术语首字母 A-Z 分组输出 ## A / ## B / ... 节;
# 中文术语归 ## 中文 节;数字术语归 ## 0-9 节;空字母节省略(只输出实际有内容的字母节)。
# PR-B (issue #28/#31):行尾 tags 默认不渲染;启用 --show-tags 开关恢复旧行为(行尾 <span>#tag</span>)。
# node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --knowledge knowledge/ --show-tags --json
```

(本步为 query/synthesize 共享;ingest 跑完调一次,确保 index.md 反映新页)

写入行为(issue #11 起):

- **sentinel 路径**:`index.md` / `glossary.md` 含 `<!-- AGGREGATE-START -->` / `<!-- AGGREGATE-END -->` 标记对时(issue #11 修复后的 init 产物默认含),脚本**删除两个标记之间的全部旧内容,在 END 标记前重写当前 knowledge/ 实际状态的索引数据**;标记之外的手写区(Overview、维护备注、手工术语批注)原样保留。
- **占位清理**:init 模板的占位段(`## Sources({数量})`、A-Z `*(暂无)*` 字母节等)都在标记内,首次聚合后被真数据替换,不再「占位 + 真数据」并存。
- **glossary 分组**(PR-B #29):动态区按术语首字母分组输出 `## A` / `## B` / ... / `## Z` 节;中文术语归 `## 中文` 节(用 `[一-鿿]` 判断);数字术语归 `## 0-9` 节;**空字母节省略**(只输出实际有内容的字母节)。每个术语条目行结构:`- **term** —— 参见 [page-title](./path):description`。
- **幂等**:同状态连跑两次,sentinel 区间内容一致,不累积。
- **向后兼容**:文件不含标记对(存量 wiki)→ 保持 v0.6.4 行为(按模板 + 动态区全量重建),不迁移、不把存量文件 sentinel 化。

### 步骤 15:更新 index.md

由 aggregate-index.js(步骤 14)统一处理,幂等;写入方式为**替换 index.md 中 sentinel 标记区间的内容**(手写区保留),无标记对的存量文件保持 v0.6.4 全量重建行为。

- **行结构**(PR-B #28 / #31 契约):每行 = `[title](link) —— description`(entity / concept / analysis / comparison / synthesis)或 `[[wikilink|alias]] —— description [status]`(source)。
- **行尾 tags 默认不渲染**:`<span style="color:gray">#tag1 #tag2</span>` 默认省略(避免灰底冲淡 description,符合 #28 推荐 A 方案);`tags` 字段在 `frontmatter.tags` 读,不在 list 行展示。
- **--show-tags 开关**:显式传 `--show-tags` 时恢复旧行为(行尾输出灰色 `<span>` 包装,#31 兼容);默认不传 = 不渲染。
- **LLM 不再手工删除 tags 行**:脚本统一控制,不需要在 step 15 之后用 Edit 删 `<span>` 行。
- 6 处 tags 渲染(source / entity / concept / analysis / comparison / synthesis)统一走 `renderTagsLineSuffix(fm, {showTags})` 共用函数(对齐 #31)。

### 步骤 16:更新 overview.md

overview.md 不由 aggregate-index.js 自动重建,改由 LLM 在"大图变化时"(新增 source / 完成 synthesis / 累计 analyses > 10 等)按 plugin 仓 `doc/template/page-overview.md` 骨架(在用户工程为 `doc/templates/page-overview.md`)增量更新:

- 保留已有骨架(一句话定位 / 主题领域分布 / 知识成熟度 / 未覆盖领域 / 维护 五节)
- 按当前 knowledge/ 实际状态刷新"主题领域分布"与"知识成熟度"两节的引用
- "未覆盖领域"由 LLM 读 log.md 近 30 天 query + knowledge/ 缺口自行判断

### 步骤 17:追加 log.md(最新在前,ISO 8601)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/append-log.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 已有当天 H2 → 复用
- 无 → 插入新 H2 (最新在前)
- `**Ingest**` 行 wikilink 优先用 `batch.files[].slug`(不是 inbox 原文件名 basename);raw 路径用 `{slug}.{原扩展名}`。inbox 来源路径保留原文件名(人类追溯用)。
- **PR-C (v0.6.6) entity/concept 抽取列**:若 `batch.files[].entities[]` / `batch.files[].concepts[]` 非空(步骤 3 已声明),脚本自动在 `**Ingest**` 行末尾追加 `+ entities/<dir>/<slug>.md + concepts/<dir>/<slug>.md`(元素 schema `{type, slug, title?}` 对齐 build-related-pages.js:697-700;type 子类 `entity.person` → 目录 `person`,剥 `entity.` 前缀)。LLM 无需手工补 entity/concept 列,知识图谱变化追溯完整(修复 issue #30);格式对齐 `doc/template/page-log.md` 模板示例。

### 步骤 18:清理 temp/

```bash
rm temp/ingest-batch-{ts}.json
# raw_backup_{hash}/ 保留(用户可能想找回旧版)
```

### 步骤 19:lint C17/C18/C19 校验本次产出

调 lint skill(M2.4 实现)校验 C17(模板一致性)/ C18(原生+副本矛盾)/ C19(降级日志);FAIL 必须修复后才算 ingest 完成。

当前为 M2.4 预留 stub:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/lint-stub.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --project <用户工程根> --json
```

读 stdout JSON:

- `linted` 字段:扫到的 knowledge/ 页数
- `fail`:规则 R7.2(frontmatter `updated` 非 ISO 8601)失败数;`>0` → exit 2(FAIL 必须修复后才算 ingest 完成)
- `warn`:规则 R7.1(frontmatter `tags` < 5 条)+ **R7.3(reserved filename 误含 frontmatter)** + C21 命中数;`>0` → WARN(建议修复)
- `warnings_by_file` / `errors_by_file`:聚合到文件级别,SKILL.md 可按路径展示
- M2.4 真实实现替换 stub 内容,字段含义不变。

**reserved filenames 豁免**(对齐 `doc/schema/frontmatter-spec.md §3.3` plugin 扩展 reserved + OKF §3.2):

- reserved filenames:**`index.md` / `log.md` / `overview.md` / `glossary.md`**
- **不参与** R7.1(tags < 5)/ R7.2(updated 非 ISO 8601)(这两个规则的前提是文件有 frontmatter,reserved file 没有所以无意义)
- **R7.3(WARN)**:reserved file 误含 `^--- ... ---` frontmatter 块 → 报告到 `warnings_by_file`,**不改文件**(用户 / `aggregate-index.js` 自决)
- C21(只对 `type: source` 触发)对 reserved file 天然不触发(其 `fm.type` 不为 `'source'`),无需额外豁免

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 0 | temp/ 残留 batch 处理 | 等用户明确 |
| 步骤 2 | 路径 4 paddleocr 未装 → 装 / 跳过 | 不静默降级(G6) |
| 步骤 3 | raw 子目录 + 命名飘 + entity/concept 抽取 | 等用户明确 |
| 步骤 4 | dry-run diff 确认 + 冲突决策 [y/n/d] | 等用户明确 |
| 步骤 5 | 提取要点对话 | 可跳过 |
| 步骤 18 | 是否删 batch.json | 等用户明确 |

## 失败语义(权威源 = implement-ingest.md §6.1)

失败语义表权威源:[doc/design/implement-ingest.md §6.1](../doc/design/implement-ingest.md#61-失败语义权威源-v056-起-skillmd-引用此处)。G3 / G6 / G10 三条规则覆盖:

- **G3** `convert-to-md.js` spawn 失败(任意路径 3/4)
- **G6** ajv schema 校验失败(任意 frontmatter)
- **G10** preflight 缺依赖 / plugin-root 不存在

其他场景(`move-to-raw` 同名冲突等用户拍板门场景)归 SKILL.md 步骤 4 处理,**不**纳入 G3/G6/G10。

## 不做什么(SKILL.md 边界)

- 不发明 frontmatter 字段
- 不调 LLM API(脚本部分纯机械)
- 不写 `safe-mv.py` / `convert-to-md.py` / `dedupe.js` / `auto-tag.js` / `auto-extract.js`(LLM 决策归 SKILL.md 管)
- 不引入 npm 依赖(0 个新增,只用现有 `@firecrawl/anydoc` + `js-yaml` + `ajv`)
- 不自动 commit
- 不调 git / SVN / Mercurial
- 不写 Node.js daemon / RAG / embedding / watcher(NFR-1)
- 不自动 `npm install` / `pip install`;缺依赖 → FAIL + SKILL.md 提示用户手动装

## 回滚点

- 步骤 0-2 之间:**无副作用**,可任意重跑
- 步骤 4 之前:inbox 文件未动;任意重跑
- 步骤 4 `--apply` 之后:从 `temp/raw_backup_{hash}/` 恢复
- 步骤 12 之后:反链写坏 → 重跑 build-related-pages(追加模式会累积;需清理 → 手工删除对应 H2 区块再跑)
- 步骤 17 之后:log.md 写错 → 手改 + 重跑 ingest

## 引用

- 设计文档:`doc/design/implement-ingest.md`
- 上游契约:`doc/design/prd.md` §4.2 + `doc/design/design.md` §3.2 / §4.2 / §6
- 字段权威:`doc/schema/frontmatter-spec.md` §4.1.1 + §11.7
- 工作流入口:`doc/schema/schema.md` §1.1
- 已有可复用:`scripts/gen-page.js` + `scripts/aggregate-index.js` + `scripts/anydoc/*` + `scripts/ocr/ocr_to_md.py`
