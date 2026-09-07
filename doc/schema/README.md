# aeps-llm-wiki-plugin —— Schema 定义目录

> **职责**:本目录是 plugin 的 **frontmatter schema 权威定义**集中地,与 `doc/template/`(页生成模板 + 字典)分工。

---

## 1. 文件清单

| 文件 | 用途 | OKF 兼容 | init sync |
|---|---|---|---|
| `README.md` | 本文件,目录职责说明 | N/A | —— |
| `frontmatter.schema.json` | JSON Schema,机器读字段定义(跟随 spec 对齐) | ✅ | **覆盖** |
| `frontmatter-spec.md` | 字段规范 markdown,**人读字段规范,唯一权威** | ✅ | **字典 append** |

---

## 2. 权威顺序

OKF v0.2 > **`frontmatter-spec.md`(人读字段规范,唯一权威)** > `frontmatter.schema.json`(机器读,跟随 spec 对齐) > `doc/template/README.md`(人读入口,总览) > `doc/schema/schema.md`(工作流入口)

**对齐原则**:人只能读懂人读规范,`frontmatter.schema.json` 字段定义/约束/描述必须向 `frontmatter-spec.md` 对齐;两者不一致时以 `frontmatter-spec.md` 为最终裁决。

---

## 3. 引用约定

其他文件引用本目录的 schema 时,统一使用 `doc/schema/frontmatter.{schema.json, -spec.md}` 路径。详细字段说明见 [frontmatter-spec.md](./frontmatter-spec.md)。