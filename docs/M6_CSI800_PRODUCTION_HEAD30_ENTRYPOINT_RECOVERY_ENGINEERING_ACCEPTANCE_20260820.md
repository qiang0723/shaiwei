# M6-4B-R1 生产 Head30 编排入口恢复工程验收

## 结论

`GO_RECOVERY_ENGINEERING_ONLY`。原scope入口失败证据已冻结且永久禁止重跑；恢复实现只修复
Compose tmpfs序列化，并增加必须由Docker daemon实际创建容器的合成fixture。真实Qlib、封存预测、
控制报告内容和策略效果均未读取，组合转换尝试仍为0，生产授权为`none`。

## 实现边界

- 新恢复协议显式继承原协议、失败scope和机器失败证据，且机械锁定唯一变量为tmpfs序列化。
- 原release协议与scope仍可独立加载；恢复scope使用新协议ID、批准动作、镜像和批准文件路径。
- runner/auditor通过显式`--protocol`选择恢复协议，禁止任意协议路径。
- recovery Compose展开后，runner/auditor tmpfs分别为单个4g/1g挂载项；断网、只读根、非root、
  cap-drop、无env、无Docker socket、无生产账本和无整仓挂载边界不变。
- daemon级fixture服务不挂载Qlib、M6 effect、批准文件或真实输出，只运行既有纯合成双跑门。
- 恢复前置校验单独放入`recovery_validation.py`；核心`real_contract.py`保持354行，未因恢复路径增长为
  超过400行的热点文件。

## 验证

- M6 Head30原协议、发布与恢复专项：19 PASS。
- 架构宪法：13 PASS。
- 全仓：1517 PASS，17条既有第三方/兼容性warning。
- Ruff、compileall、pip check、Compose展开/语法与`git diff --check`：PASS。

## 待完成

本实现提交推送后才能构建新的不可变恢复镜像，并经daemon实际创建fixture复跑；随后生成新的精确
recovery scope并停止。未获用户绑定新scope的批准，不得启动真实runner或auditor。
