# scripts/

**当前状态**:占位目录,待与 convert-to-md.py 等脚本一起新建。

## 定位

skill 调用的辅助脚本。**只放单次运行即退出的 helper**,不开 daemon、不挂监听、不对外暴露服务(与 "plugin 不带运行时" 约束不冲突)。

**运行时栈**:**Python 3.10+ 单栈** —— scripts/ 与 hooks/ 统一一套解释器,convert-to-md 直接调 anydoc / paddleocr(无需 fork 另一栈);SKILL.md 用 `python3 ./scripts/<name>.py ...` 显式调用,避免依赖 PATH;单测用 pytest。详见 design §1.4 + §2.4。

## 调用约定(scripts/ 严禁交互,详见 design §1.4 硬契约 + Q10)

**scripts/ 是机械执行器,不是 CLI app**:禁止任何形式的运行时交互(Q10):

| 禁止调用 | 替代方案 |
|---|---|
| `input()` / `input(prompt)` | SKILL.md 在 Claude 对话层发起交互,拍板结果通过参数传入 |
| `sys.stdin.read()` / `sys.stdin.readline()` | 同上 |
| `getpass.getpass()` | 完全禁 |
| `select.select([sys.stdin], ...)` 等 stdin 等待 | 同上 |

**调用模式(Proposal-Apply 两阶段,Q10)**:

- **SKILL.md 在 Claude 对话里发起交互**(如 "文件 X 提议归档到 raw/06_功能安全/, 是否同意?")
- 用户回复后,**SKILL.md 写 `temp/decision-<hash>.md`**(详见 design §4.2.x 三段落档)
- **SKILL.md 调 `python3 ./scripts/<name>.py --apply temp/decision-<hash>.md`**
- scripts 读 decision 文件机械执行(mv / mkdir / 写 log.md / 写 knowledge/),**不发起任何 prompt**

**调用方约定**:

- ✅ **允许**:SKILL.md(Bash tool)用 `python3 ./scripts/<name>.py [args]` 显式调
- ✅ **允许**:单测用 `pytest` 调 scripts,断言返回值 / 文件副作用
- ✅ **允许**:hooks(由 Claude Code 事件驱动)调 scripts,**也不得交互**
- ❌ **禁止**:用户手动 `cd <project> && python3 scripts/convert-to-md.py` 直接跑决策性脚本(应该走 SKILL.md 拍板)
- ❌ **禁止**:scripts 内部 `os.system` / `subprocess` 调起 **第二次** 交互式 CLI(防止交互传递污染)

**lint C10.1 静态扫描断言**:`tests/test_no_daemon.py` 用 `ast` 模块扫所有 `scripts/*.py`,禁止出现上述禁止调用(详见 implement.md §C10.1)。

## 已确定要建的脚本

| 脚本 | 调用方 | 用途 |
|---|---|---|
| `convert-to-md.py` | ingest skill | 按扩展名分流:`md/txt/...` 直接读;`pptx/docx/xlsx/pdf` 先 Claude converter 失败降级 anydoc;`png/jpg/jpeg/bmp/tiff` 走 paddleocr。**支持 `--batch` 多文件模式**(inbox N ≥ 2 时走,共享 1 次 paddleocr Engine / anydoc 实例,避免 N 次冷启动叠加);SKILL.md 调用时 Bash timeout 显式 600000ms。详见 design §4.2 / §2.4 / §4.2.1 |
| `check-qmd.py` | query skill | 跑前探查:数 knowledge 页数 + 测 `qmd --version`,按阈值返回 `engine: index / qmd / fail`(详见 design §4.3 / §2.4) |
| `requirements.txt` | (依赖清单,非可执行) | anydoc / paddleocr / jsonschema / pyyaml 强依赖(未装 FAIL);pytest 单测时需要;qmd 可选(未装按阈值降级或 FAIL,详见 design §4.3)。用户必须 `pip install -r scripts/requirements.txt`,qmd 需 `npm install -g @tobilu/qmd` |

## 未来可能添加的脚本(skill 实现阶段定)

| 候选 | 调用方 | 用途 |
|---|---|---|
| `safe-mv.py` | ingest skill | 把 inbox 文件原子迁到 raw/(git mv + 校验) |
| `ensure-dirs.py` | ingest skill | `mkdir -p` raw/06_功能安全 这种二级路径 |
| `append-log.py` | 所有 skill | 写 log.md 一条记录(避免人工拼格式) |
| `validate-frontmatter.py` | lint / ingest | 按 schema/frontmatter.schema.yaml 校验字段(jsonschema) |
| `lint-orphans.py` | lint skill | 扫知识库找孤儿页/孤立页 |
| `okf-lint.py` | ingest / lint | OKF v0.2 合规校验(不维护 frontmatter `links:` 镜像,详见 design §3.6.2) |
| `okf-reader.py` | query / ingest | plugin 自实现 OKF reader,识别 `[[wikilink]]` + `[text](path.md)` 双格式 wiki link,产出 OKF `sources` 列表(详见 design §3.6.2 + `src/schema/OKF-EXTENSION.md`) |

添加前先在 [implement.md](../implement.md) 里写测试用例 + 在 [prd.md](../prd.md) 找对应 AC 锚定。