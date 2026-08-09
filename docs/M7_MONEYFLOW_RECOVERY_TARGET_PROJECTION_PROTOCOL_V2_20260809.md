# M7-0R3-P1 真实目标投影协议 v2 纠错说明

## 裁决

v1 已冻结并推送，但在任何真实证券键读取或执行前，工程测试发现其 R2 core 身份转录错误：v1 写成
`df5de399d915...eeca`，而封存 lineage report、独立 DuckDB audit 与 tracked execution manifest 三者一致为
`df5de3990428...eeca`。

因此：

- v1 永久保留，不改写，且不得生成可执行 release；
- v1 未执行、未读真实证券键、未消费研究尝试；
- v2 只纠正上述冻结前序身份，不改变 908/541 分类、日期口径、门槛、权限或输出；
- projector、auditor、镜像和 release scope 只允许绑定 v2；
- v2 实现仍须先推送，再生成精确 scope，并等待用户绑定该 scope 的批准。

## 其余协议

除 v2 YAML 的 `supersession` 留痕与 authoritative core 更正外，其余目标、PIT 日期、一次性 claim、
断网、key-only、独立审计、忽略区输出和生产隔离要求均与 v1 文档相同。
