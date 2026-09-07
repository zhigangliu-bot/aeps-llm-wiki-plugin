---
name: aeps-llm-wiki-ingest
description: 把用户丢进 inbox/ 的资料按 5 路径分流归档到 raw/ 与 knowledge/,含双向反链与 log 更新
plugin-version: 0.5.5
---

# /aeps-llm-wiki-ingest

把用户资料从 `inbox/` 迁移到 `raw/{subdir}/`,生成 `knowledge/sources/<slug>.md` 源页,抽取 entity / concept 子页,双向反链,更新 `index.md` / `log.md` / `overview.md` / `glossary.md`。

## 触发

用户在 `inbox/` 丢资料后跑 `/aeps-llm-wiki-ingest`(无参数,递归扫 `inbox/`)。

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

### 步骤 1:扫 inbox

```bash
node scripts/ingest/scan-inbox.js --inbox inbox/ --json
```

读 stdout JSON:
- `count == 0` → 提示"inbox 为空",exit 0
- `count > 0` → 进入步骤 2

### 步骤 2:5 路径分流

```bash
# 对每个文件分别调(也可用 --batch 批模式)
node scripts/ingest/classify.js --file inbox/<file> --check-deps --json
```

读 stdout JSON:
- `route == 1` → 纯文本,**不调** `convert-to-md.js`
- `route == 2` → PDF 原生可读,**不调** `convert-to-md.js`
- `route == 3` → 调 `convert-to-md.js`(PDF/HTML 走 anydoc;docx/pptx/xlsx 走 docling)
- `route == 4` → 调 `convert-to-md.js`(paddleocr);若 classify.js 返回 `fail: true` → 路径 4 不可用,询问用户装 paddleocr,**FAIL 不降级**(G6 + implement-ingest.md §1.1)
- PDF 原生失败 → 用 `--route 3` 覆盖默认(SKILL.md 显式重跑)

```bash
node scripts/ingest/convert-to-md.js --file inbox/foo.pdf --emit-to inbox/ --json
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
node scripts/ingest/init-batch.js \
  --project <用户工程根> \
  --files '<scan-inbox JSON 的 files[]>' \
  --emit-dir <用户工程根>/temp/ --json
```

读 stdout JSON `batch_file`,后续 3 步脚本都用此文件。

```bash
# dry-run 先看
node scripts/ingest/move-to-raw.js \
  --project <用户工程根> --batch <batch_file> --json

# 拍板后 --apply (若有同名冲突,先 --decision y|n|d)
node scripts/ingest/move-to-raw.js \
  --project <用户工程根> --batch <batch_file> --decision y --apply --json
```

- `[y]` 覆盖:先备份 `temp/raw_backup_{hash}/` + `os.replace()` 原子替换
- `[n]` 跳过:status=skipped,inbox 文件保留
- `[d]` 仅删旧副本

### 步骤 5:提取要点对话(可"继续"跳过)

防 spam 对话;LLM 解读产出,可让用户跳过。

### 步骤 6:建 source 页 skeleton

LLM 拍板下面 4 个 OKF 推荐字段后传入 `gen-page.js`(对齐 `templates/page-source.md` 模板头部,避免前次 M2.2 落地时的字段缺失 bug):

```bash
node scripts/gen-page.js --type source --slug <slug> \
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

写完正文后,**回头把 `--summary` 字段值写入 frontmatter**(步骤 6 重跑一次 `--out` 覆盖)。

来源不足自检:每条断言自检能否在源文件找到依据;无法溯源 → 显式标注 `[来源不足,需人工复核]`。

### 步骤 8:追加 `> 原始来源:` + Related Pages 占位

由 `gen-page.js` 自动在 `## 重点摘录` 顶部追加 `> 原始来源:` blockquote。Related Pages 占位由 build-related-pages.js(步骤 13)写。

### 步骤 9:判定 entity / concept 抽取

LLM 读 raw + `concept-entities-spec.md` 判 18 子类。

### 步骤 10:建 entity / concept 页 skeleton

```bash
node scripts/gen-page.js --type <entity|concept>.<subtype> --slug <slug> \
  --title "<title>" --json
```

### 步骤 11:LLM 填 entity / concept 正文

自由发挥。`sources[]` 字段在 gen-page 阶段已写入 plugin 骨架(指向本次 source 页的 resource 路径);若用户改 entity/concept 的 sources 引用,build-related-pages.js 步骤 12 会自动反向重建。

### 步骤 12:回填 source 页 `## 相关页面` + entity/concept 页 `## 来源资料`(双向反链,完全重建)

```bash
node scripts/ingest/build-related-pages.js \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 扫所有 source / entity / concept 页 frontmatter
- source 页 → 写 `## 相关页面(Related Pages)`(Entities / Concepts 分组)
- entity/concept 页 → 写 `## 来源资料`(按 source title 排序)
- 每次**完全重建**,不保留人工条目
- 某组空 → 省子标题;全空 → 省整节

### 步骤 13:更新已有 wiki 页

LLM 决定:命名飘合并 / 改链等。

### 步骤 14:更新 glossary.md(增量合并)

```bash
node scripts/aggregate-index.js --knowledge knowledge/ --json
```

(本步为 query/synthesize 共享;ingest 跑完调一次,确保 index.md 反映新页)

### 步骤 15:更新 index.md

由 aggregate-index.js(步骤 14)统一处理,幂等。

### 步骤 16:更新 overview.md

仅大图变化时由 LLM 决定;通常由 aggregate-index.js 自动重建。

### 步骤 17:追加 log.md(最新在前,ISO 8601)

```bash
node scripts/ingest/append-log.js \
  --project <用户工程根> --batch <batch_file> --apply --json
```

- 已有当天 H2 → 复用
- 无 → 插入新 H2 (最新在前)

### 步骤 18:清理 temp/

```bash
rm temp/ingest-batch-{ts}.json
# raw_backup_{hash}/ 保留(用户可能想找回旧版)
```

### 步骤 19:lint C17/C18/C19 校验本次产出

调 lint skill(M2.4 实现)校验 C17(模板一致性)/ C18(原生+副本矛盾)/ C19(降级日志);FAIL 必须修复后才算 ingest 完成。

当前为 M2.4 预留 stub:

```bash
node scripts/ingest/lint-stub.js --project <用户工程根> --json
```

读 stdout JSON:`linted` 字段反映本次扫到的 knowledge/ 页数;`fail` / `warn` 在 stub 阶段固定为 0;M2.4 真实实现替换 stub 内容,字段含义不变。

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 0 | temp/ 残留 batch 处理 | 等用户明确 |
| 步骤 2 | 路径 4 paddleocr 未装 → 装 / 跳过 | 不静默降级(G6) |
| 步骤 3 | raw 子目录 + 命名飘 + entity/concept 抽取 | 等用户明确 |
| 步骤 4 | dry-run diff 确认 + 冲突决策 [y/n/d] | 等用户明确 |
| 步骤 5 | 提取要点对话 | 可跳过 |
| 步骤 18 | 是否删 batch.json | 等用户明确 |

## 失败语义(对齐 implement-ingest.md §6.1)

| 场景 | 行为 |
|---|---|
| convert-to-md.js spawn 失败 | 原文件保留 inbox;batch.json status=failed;SKILL.md 步骤 19 报 FAIL |
| 路径 4 paddleocr 未装 | classify.js 返回 fail:true,exit 2;SKILL.md 询问用户装,或跳过该文件 |
| move-to-raw 覆盖 raw 已存在 | 强制拍板门 [y/n/d];[y] 必先备份 `temp/raw_backup_{hash}/` |
| build-related-pages 字段不匹配 | 跳过该 entity/concept,stderr 报 WARN;不破坏 source 页 |
| ajv 校验 entity/concept frontmatter 失败 | stderr WARN;反链略过此页 |

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
- 步骤 12 之后:反链写坏 → 重跑 build-related-pages(完全重建覆盖)
- 步骤 17 之后:log.md 写错 → 手改 + 重跑 ingest

## 引用

- 设计文档:`doc/design/implement-ingest.md`(v0.1.0 已冻结)
- 上游契约:`doc/design/prd.md` §4.2 + `doc/design/design.md` §3.2 / §4.2 / §6
- 字段权威:`doc/schema/frontmatter-spec.md` §4.1.1 + §11.7
- 工作流入口:`doc/schema/schema.md` §1.1
- 已有可复用:`scripts/gen-page.js` + `scripts/aggregate-index.js` + `scripts/anydoc/*` + `scripts/ocr/ocr_to_md.py`
