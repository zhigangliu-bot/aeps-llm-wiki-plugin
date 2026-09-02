# inbox /

> **角色**:对应 Karpathy LLM Wiki 的 `inbox/` 暂存层,**不是归档层**。
> **生成方式**:`/aeps-llm-wiki-init` 时从 `templates/inbox-readme.md` 复制。
> **修改权限**:**plugin 主**。本文件不参与字典 append 同步策略,plugin 升级时直接覆盖;本地用户修改下次升级会丢失,如有定制需求请改用独立副本文档
> **本文件权威**:描述 inbox 行为边界(放什么 / 不放什么 / 清理节奏),以本文件为最终口径

---

## 这层放什么

把**还没分类、想稍后整理到 wiki**的资料随手丢这里:

- 微信截图 / 邮件附件 / 同事转过来的 PDF
- 浏览时 Ctrl+S 下来的网页 / 临时实验记录
- 会议纪要草稿 / OCR 截图
- 任何"现在没空管,但将来想沉淀进知识库"的零散文件

**支持格式**:`.md` / `.txt` / `.pdf` / `.docx` / `.png` / `.jpg`(LLM 通过 Claude 内置 converter 读取)

## 这层不放什么

- ❌ 已经归档过的资料 → 直接放 `raw/<子类>/`,**不要**再丢 inbox
- ❌ LLM 写出来的知识页 → 应放 `knowledge/sources/` / `entities/` / `concepts/`
- ❌ 需要长期保留的项目代码 / 文档 → 应在 git 仓库里,本 inbox 只是"待办漏斗"

## 放完怎么办

跑 ingest skill,让 LLM 帮你分类 + 生成知识页:

```
/aeps-llm-wiki-ingest inbox/
```

LLM 会:

1. 读源文件,提议归档到 `raw/<子类>/`(15 类边界见 `raw/README.md`)
2. **目录已存在(init 预建的 15 类)→ 无需拍板,直接迁移**
3. **目录不存在(自定义目录 / 二级子目录)→ 必须人工拍板才创建**
4. 自动生成 `knowledge/sources/<basename>.md`,抽取 entity/concept 子页

### 跳过分类交互(高级)

如果你**已经知道**该归档到哪个子类(比如这次丢的是 S32G 数据手册),可以一步到位:

```
/aeps-llm-wiki-ingest --raw-subdir=02_芯片 inbox/s32g-datasheet.pdf
```

**注意**:`--raw-subdir` **仅对 inbox 路径生效**;对 `raw/<path>` 来源不生效(raw 已归档,要走 `git mv` 手工调整)。

## 不变量

- inbox 文件**绝不静默迁出**,必须经 ingest skill + 拍板门
- 你手动 `rm inbox/<file>` 也算合法操作(只是失去"留底"),但 LLM 不会主动帮你删
- 整个 `inbox/` 目录**可以整体提交进 git**(暂存性质,体积可控);若资料含敏感信息请用 `.gitignore` 排除

## 清理建议

- **每周**:`ls inbox/` 扫一眼,丢了的都跑 ingest
- **每月**:`ls -la inbox/` 看体积,> 1 GB 时主动清掉已 ingest 的(虽然不会自动删,留作"后悔药")
