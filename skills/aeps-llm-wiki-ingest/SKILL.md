---
name: aeps-llm-wiki-ingest
description: 把用户丢进 inbox/ 的资料按 5 路径分流归档到 raw/ 与 knowledge/,含双向反链与 log 更新
plugin-version: 0.6.0
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/preflight.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/classify.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/convert-to-md.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/init-batch.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/move-to-raw.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/build-related-pages.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/append-log.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/lint-stub.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT}*),Bash(ls temp/ingest-batch-*.json*),Bash(rm temp/ingest-batch-*)
---

## Change History

- 2026-09-08 / 批次 1 / R1 (P0-1):顶部新增"脚本路径约定"段;说明 `${CLAUDE_PLUGIN_ROOT}` 由调用方注入,或用 `--plugin-root` CLI 参数显式传递冗余兜底;明确脚本位于 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- 2026-09-08 / 批次 1 / R2 (P0-2):`build-related-pages.js` 支持 `--plugin-root` / `--schema-path` / `--project` CLI 参数,schema 路径按候选列表查找(用户工程 `schema/` > 用户工程 `doc/schema/` > plugin 自检)。
- 2026-09-08 / 批次 1 / R3 (P0-3):`gen-page.js` 支持 `--plugin-root` CLI 参数,版本号 fallback 从伪零版本字符串(回退兜底)改为占位语义字符串 `"unknown"`(无法定位 plugin 根时的显式标识)。
- 2026-09-08 / 批次 1 / R4 (P0-1/2/3):命令行全部追加 `--plugin-root ${CLAUDE_PLUGIN_ROOT}` 参数,确保 `${CLAUDE_PLUGIN_ROOT}` env 未注入时仍能跑通。
- 2026-09-08 / 批次 3 / R1 (P1-3):`init-batch.js` 支持 `--files-file <absolute>` 从文件读 JSON 列表,与 `--files <json>` 互斥(都传/都不传 → ERROR)。SKILL.md 步骤 4 命令行按文件大小选择其一。
- 2026-09-08 / 批次 3 / R2 (P1-4):`append-log.js` JSON output 增加 `entries: [{file, action, summary}]` 数组,`action ∈ {added, merged, skipped}`。
- 2026-09-08 / 批次 3 / R3 (P1-6):inline preflight 已内置到所有 ingest/init 脚本顶部,缺包立即 ERROR 并打印精确 `npm install` 命令;旧步骤 0.5 主动调用的 `preflight.js` 降级为可选,与 inline 并存。
- 2026-09-08 / 批次 3 / R4 (P2-1):`build-related-pages.js` JSON output 增加 `warnings_by_file` 字段,与已有 `warnings` 扁平数组并存。
- 2026-09-08 / 批次 3 / R5 (P2-3):`aggregate-index.js` 加 `--json` 参数时输出 `by_type` + `by_subdir` 分类统计。
- 2026-09-08 / 批次 3 / R7 (P2-5):`lint-stub.js` 步骤 19 真做两条规则:R7.1 tags <5 → WARN;R7.2 updated 非 ISO 8601 → ERROR(exit 2)。
- 2026-09-08 / 批次 4 / P3-2:步骤 0.5 措辞统一为"plugin 内置 preflight,缺包即停并给精确 `npm install <pkg>` 命令,不自动安装"。
- 2026-09-08 / 批次 4 / P3-3:"失败语义"段从独立表格改为引用 [doc/design/implement-ingest.md §6.1](../doc/design/implement-ingest.md#61-失败语义权威源-v056-起-skillmd-引用此处) 权威源(G3 / G6 / G10 三规则)。
- 2026-09-08 / 批次 5 (P4-1):**breaking** —— 路径布局表更新(`schema/` → `doc/schema/`,`templates/` → `doc/templates/`);`build-related-pages.js --schema-path` 候选从 3 项收敛为 2 项(用户工程 `doc/schema/` > plugin 自检);`gen-page.js --project` 模板查找改为 `<project>/doc/templates/`,取消 cwd 兜底。
- 2026-09-09 / 批次 7 (v0.6.2):overview.md 改由 LLM 维护。`scripts/aggregate-index.js` 停止写入 overview.md(不再被计数列表覆盖);`scripts/init/build-skeleton.js` 改读 plugin 仓 `doc/template/page-overview.md` 作为初始骨架。步骤 16 重新描述为"读 `doc/templates/page-overview.md` 骨架,LLM 增量维护"。
- 2026-09-09 / 批次 6 (issue #1/#2/#3/#4):**P0/P1 bug 修复** ——
  - **#1 init-batch.js 保留 LLM 拍板字段**(slug/target_subdir/route/converter/native_text/converted_path/...):旧版 map 重写 file 静默丢为 null,导致下游 move-to-raw fail "target_subdir 未指定"。改 spread LLM 输入 + 脚本必需默认值覆盖。**步骤 4 命令行确认**:LLM 步骤 3 拍板的 `target_subdir` / `slug` 必填;`--files` / `--files-file` JSON 内 LLM 决策字段会透传到 batch.files[]。
  - **#2 gen-page.js 加 `--patch-frontmatter-only` flag**:旧版 `--out` 重跑会覆盖 LLM 已填正文为占位符。**步骤 7 改为**:写完正文后**不要**重跑 `gen-page.js --out`,改用 `gen-page.js --out foo.md --patch-frontmatter-only --summary "..." --title "..."` 只 patch frontmatter,正文原样保留。目标文件不存在 → fallback 全量生成(WARN)。
  - **#3 aggregate-index.js 聚合页注入最小 frontmatter**:index.md / overview.md / glossary.md 加 `type` / `title` / `updated` (ISO 8601) / `generated` / `status: stable` / `tags` 5 项;旧版只有 `---` 水平线,lint R7.2 FAIL。**步骤 14-16 行为不变**(脚本输出新格式,聚合内容照旧)。
  - **#4 append-log.js wikilink 优先用 slug**:旧版用 inbox 原文件名 basename,slug 重命名后 wikilink 指向不存在文件。改 `resolveDisplaySlug(file) → file.slug || path.basename(path, ext)`。**步骤 17 命令行确认**:LLM 步骤 3 必填 `slug`(已经必填,本次只改显示逻辑)。

## 脚本路径约定(批次 1,2026-09-08)

> **脚本路径约定**:本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin-root;该变量由调用方注入(plugin 自动注入或用户 shell 导出),或通过 `--plugin-root` CLI 参数显式传递冗余兜底。

- 脚本均在 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- 默认调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT} ...`(env 已注入)
- 兜底调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/scan-inbox.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --plugin-root ${CLAUDE_PLUGIN_ROOT} ...`(env 注入失败时显式冗余)
- `build-related-pages.js` 还支持 `--schema-path <absolute>` 显式覆盖 schema 路径;支持 `--project <绝对路径>` 显式指定用户工程根。
- `gen-page.js` 还支持 `--project <绝对路径>` 显式指定用户工程根(模板路径解析用)。
- 当 `${CLAUDE_PLUGIN_ROOT}` env 未注入(plugin loader 未生效 / shell 没 export),`--plugin-root` 是唯一兜底,**必须**显式传。

# /aeps-llm-wiki-ingest

把用户资料从 `inbox/` 迁移到 `raw/{subdir}/`,生成 `knowledge/sources/<slug>.md` 源页,抽取 entity / concept 子页,双向反链,更新 `index.md` / `log.md` / `overview.md` / `glossary.md`。

## Change History

- v0.5.6 (2026-09-08,批次 2 P1 修复):
  - **move-to-raw 按 slug 重命名**:`batch.files[]` 提供 `slug` 字段后,文件按 `{slug}.{ext}` 落地到 `raw/<subdir>/`,原扩展名保留。已存在同名 slug → SKIP + WARN,不覆盖;slug 非法 → ERROR。详见步骤 4。
  - **build-related-pages 改追加模式**:`## 相关页面` / `## 来源资料` 区块默认保留人工写的条目,新反链追加在末尾(去重);同 wikilink 重复 → 保留人工条目 + stderr WARN。如需完全重建,先手工删除区块再跑。详见步骤 12。
  - **gen-page --project 参数**:模板查找 `--project <absolute>` 优先级(> `env.WIKI_PROJECT`;v0.5.8 起取消 cwd 兜底);`--project` 显式传入时严格从 `<project>/doc/templates/` 找,找不到 → 清晰 ERROR。详见步骤 6/10。
  - **ajv date-time WARN 降级**:`doc/schema/frontmatter.schema.json` 把 `format: "date-time"` 替换为等价的 `pattern` 校验,跑 ajv 时不再打印 `unknown format "date-time" ignored` 噪音。零新增 npm 依赖。

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

v0.5.8 起用户工程文档层与 plugin 仓对齐(都在 `doc/` 下),脚本路径不再需要区分两套命名空间。历史背景:旧布局用户工程根是平级的 `schema/` `templates/`,曾引发脚本路径混淆与 `junction doc/schema → schema` 误用;v0.5.8 已根治。

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

### 步骤 0.5:依赖 preflight(可选,v0.5.6 起)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/preflight.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --scripts-dir <用户工程根>/scripts --json
```

读 stdout JSON:

- `ok == true` → 进入步骤 1
- `ok == false` → 缺失依赖,按 stderr `npm install` 提示让用户装,exit 0 后重跑本步

**为什么单独一步**:SKILL.md L253 / L257 已规定不自动 `npm install`,但没规定 preflight 时机,导致用户首次跑步骤 1 才遇到 `Cannot find module 'js-yaml'` 类错误才意识到要装。preflight 把错误前置到流程最早节点。

> **v0.5.6 批次 3 修订**:inline preflight 已内置到所有 ingest/init 脚本顶部(`scripts/lib/preflight.js` 的 `requireDeps` 函数),缺包时脚本启动即 ERROR 并打印精确 `npm install <pkg>` 命令。本步降级为可选,跳过即可(若 LLM 跳步骤 1,inline 仍会拦截)。

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
- `target_subdir` ∈ 15 raw 子目录字典(`doc/template/rawdir-spec.md`)
- 每抽 entity / concept 提议 slug(对齐 `concept-entities-spec.md` 14 子类判定)

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
# 文件多 / 路径含中文+空格 / 转义麻烦 → 落 temp/batch.json,走 --files-file(批次 3 P1-3 修复)
echo '<scan-inbox JSON 的 files[]>' > temp/batch.json
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/init-batch.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> \
  --files-file <用户工程根>/temp/batch.json \
  --emit-dir <用户工程根>/temp/ --json
```

> `--files` 与 `--files-file` 互斥(二选一,都传/都不传 → ERROR exit 1)。

> **v0.6.0 批次 6 修订**(issue #1 fix):JSON 数组里 LLM 步骤 3 拍板的字段(`slug` / `target_subdir` / `route` / `converter` / `native_text` / `converted_path` / 等)会**完整透传**到 `batch.files[]`;旧版会把这些静默丢为 null,导致下游 `move-to-raw` fail "target_subdir 未指定"。

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
- **v0.5.6 起(批次 2 P1-1)按 slug 重命名**:若 `batch.files[]` 提供 `slug` 字段,文件按 `{slug}.{ext}` 落地(原扩展名保留)。slug 已存在 → SKIP + WARN 不覆盖;slug 非法 → ERROR。

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

> **v0.5.6 起必传 `--project`(v0.5.8 起路径为 doc/ 层级)**:模板查找严格从 `<project>/doc/templates/` 读,找不到 → ERROR。`--project` 解析顺序:`--project` CLI > `env.WIKI_PROJECT`(v0.5.8 起取消 cwd 兜底)。

参数说明:

- `--description`:OKF v0.2 §4.1 推荐字段;`template/page-source.md` 已含示例。LLM 根据标题 + 文件名给一句话 30-80 字概括
- `--tags`:6 轴字典(`doc-spec.md`),必填 `docform/` + `domain/`,共 5-10 条
- `--summary`:OKF v0.2 §4.1 推荐字段;LLM 写完正文后回到 frontmatter 补,50-150 字
- `--stale-after`:默认 `generated.at + 1 年`(ISO 8601);LLM 可根据资料类型调整(标准/规范 → 5 年;时事 → 6 月)
- `--source-file`:Obsidian wikilink,`[[<subdir>/<slug>.<ext>|<display>]]` 格式;`template/page-source.md` 示例参考

如果 4 个字段 SKILL.md 一时拿不准,**步骤 7 写完正文后回步骤 6 补传**重跑(`--out` 覆盖目标文件)。

### 步骤 7:LLM 填 source 正文

仅改 H2 之间正文;**不**改 frontmatter 字段值 / H2 顺序 / `## 维护说明` 尾巴(对齐 design §4.3 SKILL.md 硬约束)。

**v0.5.9 起强 prompt**:LLM 读完源文件后,**先**问自己:**这篇 source 有什么独特结构?** 在 `## 重点摘录` 之前用 1-N 个 H2 节呈现(占位骨架 `## 阅读路线` 强烈建议改名,如 `## 来源元信息` / `## 核心要点` / `## 关键引用` / `## 适用范围` / `## 术语定义` / `## 关键约束` / `## 技术原理` / `## 性能指标` / `## 与同类对比` / `## 研究背景` / `## 方法` / `## 结果` / `## 结论` 等)。极短源文件可保留占位名 + 一句豁免说明。**所有自由追加节强制溯源**(lint C21 WARN)。

**正文书写顺序**:`# 标题` → **[自由追加节 1..N]** → `## 重点摘录` → `## 我的思考` → `## 总结:最有收获的一句话` → (脚本追加 `> 原始来源:` blockquote + Related Pages 占位)。

写完正文后,**回头把 `--summary` 字段值写入 frontmatter**(v0.6.0 起改用 `--patch-frontmatter-only`,**不**重跑 `--out` 全量覆盖)。

```bash
# v0.6.0 起 (issue #2 fix):只 patch frontmatter,正文原样保留
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --type source --slug <slug> --ext <ext> \
  --out <已存在的目标文件.md> \
  --patch-frontmatter-only \
  --summary "<补 50-150 字精要>" --title "<如有调整>"
```

> **v0.6.0 起步骤 7 重大变更**:旧版"步骤 6 重跑一次 `--out` 覆盖"会**覆盖 LLM 已填正文**为占位符。改用 `--patch-frontmatter-only` 只 patch frontmatter;目标文件不存在 → fallback 全量生成(WARN stderr)。

来源不足自检:每条断言自检能否在源文件找到依据;无法溯源 → 显式标注 `[来源不足,需人工复核]`。

### 步骤 8:追加 `> 原始来源:` + Related Pages 占位

由 `gen-page.js` 自动在 `## 重点摘录` 顶部追加 `> 原始来源:` blockquote。Related Pages 占位由 build-related-pages.js(步骤 13)写。

### 步骤 9:判定 entity / concept 抽取

LLM 读 raw + `concept-entities-spec.md` 判 18 子类。

### 步骤 10:建 entity / concept 页 skeleton

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --type <entity|concept>.<subtype> --slug <slug> \
  --title "<title>" --json
```

**entity.* / concept.* 通用骨架**(v0.5.7 起):`gen-page.js` 按 `entity.<subtype>` 自动选 [`page-entity.md`](../doc/template/page-entity.md);按 `concept.<subtype>` 自动选 [`page-concept.md`](../doc/template/page-concept.md)。**不再**使用旧的 7 个差异化模板(`page-entity-{person,organization,project,product,event,place,other}.md` / `page-concept-{theory,method,field,phenomenon,standard,term,other}.md`,已删除)。子类差异通过 `type` 字段 / `aliases` / `tags` / 自由正文组织,**不**用 H2 节名体现。

### 步骤 11:LLM 填 entity / concept 正文

自由发挥。`sources[]` 字段在 gen-page 阶段已写入 plugin 骨架(指向本次 source 页的 resource 路径);若用户改 entity/concept 的 sources 引用,build-related-pages.js 步骤 12 会自动反向重建。

### 步骤 12:回填 source 页 `## 相关页面` + entity/concept 页 `## 来源资料`(双向反链,**追加 + 保留**)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/build-related-pages.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 扫所有 source / entity / concept 页 frontmatter
- source 页 → 写 `## 相关页面(Related Pages)`(Entities / Concepts 分组)
- entity/concept 页 → 写 `## 来源资料`(按 source title 排序)
- **v0.5.6 起改为追加模式**:每次 ingest 在区块末尾追加新确认的反链(去重 wikilink 字符串);**保留** 区块下所有现有条目(含人工补的)。
- 同 wikilink 重复 → 保留人工条目(可能带更详细批注),stderr WARN `duplicate wikilink [[xxx]] 已在人工条目中存在,保留人工条目`。
- **若需完全重建**,先手工删除 `## 相关页面(Related Pages)` / `## 来源资料` 区块再跑脚本。
- 区块不存在 + 本次有反链 → 新建区块;区块不存在 + 本次无反链 → 文件不动(action=`*-unchanged`)。
- 某组空 → 省子标题;全空 → 省整节(仅当区块不存在时;区块已存在则保留人工条目)。

### 步骤 13:更新已有 wiki 页

LLM 决定:命名飘合并 / 改链等。

### 步骤 14:更新 glossary.md(增量合并)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --knowledge knowledge/ --json
```

(本步为 query/synthesize 共享;ingest 跑完调一次,确保 index.md 反映新页)

### 步骤 15:更新 index.md

由 aggregate-index.js(步骤 14)统一处理,幂等。

### 步骤 16:更新 overview.md

**v0.6.2 起不再由 aggregate-index.js 自动重建**。overview.md 改由 LLM 在"大图变化时"(新增 source / 完成 synthesis / 累计 analyses > 10 等)按 plugin 仓 `doc/template/page-overview.md` 骨架(在用户工程为 `doc/templates/page-overview.md`)增量更新:

- 保留已有骨架(一句话定位 / 主题领域分布 / 知识成熟度 / 未覆盖领域 / 维护 五节)
- 按当前 knowledge/ 实际状态刷新"主题领域分布"与"知识成熟度"两节的引用
- "未覆盖领域"由 LLM 读 log.md 近 30 天 query + knowledge/ 缺口自行判断

aggregate-index.js 不再覆写 overview.md,避免 LLM 维护的大图被计数列表覆盖。

### 步骤 17:追加 log.md(最新在前,ISO 8601)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/append-log.js --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 已有当天 H2 → 复用
- 无 → 插入新 H2 (最新在前)
- **v0.6.0 起(issue #4 fix)`**Ingest**` 行 wikilink 优先用 `batch.files[].slug`**(不是 inbox 原文件名 basename);raw 路径用 `{slug}.{原扩展名}`。inbox 来源路径保留原文件名(人类追溯用)。

### 步骤 18:清理 temp/

```bash
rm temp/ingest-batch-{ts}.json
# raw_backup_{hash}/ 保留(用户可能想找回旧版)
```

### 步骤 19:lint C17/C18/C19 校验本次产出

调 lint skill(M2.4 实现)校验 C17(模板一致性)/ C18(原生+副本矛盾)/ C19(降级日志);FAIL 必须修复后才算 ingest 完成。

当前为 M2.4 预留 stub(v0.5.6 批次 3 P2-5 起真做两条最小规则):

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/lint-stub.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --project <用户工程根> --json
```

读 stdout JSON:

- `linted` 字段:扫到的 knowledge/ 页数
- `fail`:规则 R7.2(frontmatter `updated` 非 ISO 8601)失败数;`>0` → exit 2(FAIL 必须修复后才算 ingest 完成)
- `warn`:规则 R7.1(frontmatter `tags` < 5 条)命中数;`>0` → WARN(建议修复)
- `warnings_by_file` / `errors_by_file`:聚合到文件级别,SKILL.md 可按路径展示
- M2.4 真实实现替换 stub 内容,字段含义不变。

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

> **失败语义表权威源已迁移到 [doc/design/implement-ingest.md §6.1](../doc/design/implement-ingest.md#61-失败语义权威源-v056-起-skillmd-引用此处)**(v0.5.6 起,P3-3 修复)。
>
> 本节不再独立维护失败语义表,改为引用。G3 / G6 / G10 三条规则覆盖:
>
> - **G3** `convert-to-md.js` spawn 失败(任意路径 3/4)
> - **G6** ajv schema 校验失败(任意 frontmatter)
> - **G10** preflight 缺依赖 / plugin-root 不存在
>
> 其他场景(`move-to-raw` 同名冲突等用户拍板门场景)归 SKILL.md 步骤 4 处理,**不**纳入 G3/G6/G10。



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

- 设计文档:`doc/design/implement-ingest.md`(v0.1.0 已冻结)
- 上游契约:`doc/design/prd.md` §4.2 + `doc/design/design.md` §3.2 / §4.2 / §6
- 字段权威:`doc/schema/frontmatter-spec.md` §4.1.1 + §11.7
- 工作流入口:`doc/schema/schema.md` §1.1
- 已有可复用:`scripts/gen-page.js` + `scripts/aggregate-index.js` + `scripts/anydoc/*` + `scripts/ocr/ocr_to_md.py`
