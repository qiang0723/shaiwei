# M6-4B 生产 Head30 转换器发布工程协议（结果盲）

## 裁决

本节点只建设一次性 runner、内部 replay、独立 auditor、隔离 Docker 和精确 release scope，
不读取封存预测或收益数值，不挂载真实 Qlib，不运行真实回测，也不消耗组合尝试。

## 唯一研究变量

- 分数：只复用 M6-2 `clean_lgbm_control_v1` 的 W1–W6 封存预测。
- 对照：封存的 `Top30/n_drop3` 日报，仅在未来获批运行中作为只读对照，不重跑。
- 处理：确定性 `score降序、证券代码升序` 取前30，等权、全目标替换、目标投资比例1.0。
- 其余窗口、账户、调仓周期、成交价、费用和 G0 门槛全部不变。

## 工程边界

1. runner 单次启动，内部完整执行 `first_pass` 与 `replay`；两遍处理结果物理一致，否则阻断。
2. auditor 是第二个进程，不挂载 Qlib 或封存输入，不导入 runner、execution、主指标模块，
   只从不可变输出独立重算 G0 与诊断。
3. 真实 runner 只读挂载 Qlib、M6 封存 effect、M6 独立审计、release scope 和 approval；
   只写专用忽略目录，不挂载生产账本、`.env`、Docker socket 或完整项目目录。
4. 当前只允许纯合成 fixture 验证。首次获批读取处理效果时才消耗1次
   `m6_portfolio_converter` 尝试；失败也消耗，同 scope 不得重跑。
5. 所有结论都不授权生产，也不回答50万元最小手数和资金可行性。

## 停止条件

实现、合成验收、不可变镜像和精确 scope 均完成并推送后立即停止，向用户提交包含 scope SHA-256
的完整授权句。未获得该精确授权前，真实预测、控制报告和收益保持未读。
