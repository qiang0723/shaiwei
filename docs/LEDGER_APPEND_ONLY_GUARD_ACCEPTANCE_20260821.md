# 账本提交链追加门验收

## 结论

`PASS`。`make check-ledger` 不再只比较 `HEAD -> 工作树`，而是同时覆盖：

1. 提交前：`HEAD -> Git index -> 工作树`；
2. 提交后：`HEAD^ -> HEAD`；
3. 历史纠偏：只接受精确父子提交、精确账本路径、前后 Git blob SHA-256 和固定证据哈希共同命中的
   一次性例外。

这道门直接覆盖 2026-08-21 的失误模式：工作树包含自然追加和历史补录，但 Git index 只暂存历史
补录。该模式下 `HEAD -> index` 仍成立，`index -> 工作树` 不成立，机器必须在 commit 前失败关闭。

## 实现

- `tests/test_ledger_append_only.py`：
  - 对全部 41 份 Git 已跟踪 ledger 逐一检查 HEAD、index 和工作树前缀链；
  - 对全部 41 份 ledger 逐一检查当前提交相对第一父提交的追加性；
  - 强制 `git ls-files ledger/*.csv` 与受控清单集合完全相等，新增、删除或漏登记都失败关闭；
  - 对新账本继续要求首次提交只含 schema 表头；
  - 增加局部暂存回归样例；
  - 逐项验证例外记录、父子关系、Git blob、收据和说明文档身份。
- `config/ledger_append_only_exceptions_v1.json`：只登记提交 `601a782479f73aedef7860403e69708291ec3782`
  相对 `f548cbdd12e27648e202081e463fad70207a3c69` 的一次性实验账本基线纠偏；例外清单自身 SHA-256
  固定在测试中，不能静默扩展或使用通配路径。
- `make check-ledger` 与 `make test` 继续使用同一测试真身，不形成第二套检查口径。

## 验证

- 账本专项：86 PASS；
- 局部暂存对抗样例：按预期失败关闭；
- 架构门：13 PASS；
- 全仓：1,694 PASS，17 条既有第三方/未来行为提示；
- Ruff、`git diff --check`：PASS。

## 边界

- 本节点不修改任何 ledger 行、研究结果、模型、回测、模拟仓、Web、scheduler 或生产配置。
- 对历史提交的检查使用 Git blob 原始 SHA；对工作树追加检查沿用现有文本换行规范化口径，以兼容
  scheduler 已有 CSV 写入方式，但记录顺序和文本内容仍必须保持前缀。
- 本门不解决旧 runner 的尝试登记权限设计，也不设计退市处置；两项继续要求新的版本化协议和授权。
