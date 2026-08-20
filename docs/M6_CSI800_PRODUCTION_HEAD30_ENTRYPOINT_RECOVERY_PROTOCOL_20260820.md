# M6-4B-R1 生产 Head30 编排入口恢复协议（结果盲）

## 目标

只修复原scope在容器创建前暴露的Compose `tmpfs`序列化错误，增加daemon级容器创建fixture，
重新构建不可变镜像并生成新scope。原scope永久关闭，不修改、不重跑。

## 唯一改动

- runner的tmpfs必须被Compose解析为单项`/tmp:rw,noexec,nosuid,size=4g,mode=1777`。
- auditor的tmpfs必须被Compose解析为单项`/tmp:rw,noexec,nosuid,size=1g,mode=1777`。
- fixture必须实际经过Docker daemon创建隔离容器，不能只依赖`compose config --quiet`。

策略公式、Head30转换、六窗口、输入身份、G0、成本、模型、预测、runner内部双跑、独立audit和
生产授权均不变。恢复工程期间不得挂载或读取Qlib、M6 effect语义、收益、选股或控制报告内容。

## 一次性边界

原scope已调用且在容器创建前失败，真实效果读取0、组合尝试0；其`same_release_retry_authorized=false`
永久生效。恢复工程完成后生成新的精确scope并再次停止，只有用户绑定新scope SHA批准后，才允许
唯一runner + replay + 独立auditor；新scope同样不得重跑，生产授权始终为`none`。
