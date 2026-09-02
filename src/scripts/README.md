# scripts/

**当前状态**:占位目录,无脚本。

## 定位

skill 调用的辅助脚本。**只放单次运行即退出的 helper**,不开 daemon、不挂监听、不对外暴露服务(与 "plugin 不带运行时" 约束不冲突)。

## 当前为什么是空的

prd/design 阶段不写具体脚本 —— 脚本需求由 skill 实现细节确定,避免提前写过时被推翻。

## 未来可能添加的脚本(skill 实现阶段定)

| 候选 | 调用方 | 用途 |
|---|---|---|
| `safe-mv.sh` | ingest skill | 把 inbox 文件原子迁到 raw/(git mv + 校验) |
| `ensure-dirs.sh` | ingest skill | `mkdir -p` raw/06_功能安全 这种二级路径 |
| `append-log.sh` | 所有 skill | 写 log.md 一条记录(避免人工拼格式) |
| `validate-frontmatter.py` | lint / ingest | 按 schema/frontmatter.schema.yaml 校验字段 |
| `lint-orphans.py` | lint skill | 扫知识库找孤儿页/孤立页 |
| `okf-lint.py` | ingest / lint | OKF v0.2 合规校验 |

添加前先在 [implement.md](implement.md) 里写测试用例 + 在 [prd.md](prd.md) 找对应 AC 锚定。