# M6-4B 生产 Head30 转换器发布工程验收

## 结论

`GO_RELEASE_ENGINEERING_ONLY`。一次性真实 runner、内部 replay、独立 auditor、不可变产物合同、
隔离 Docker 和 release scope 生成器已实现；真实 Qlib、封存预测、控制报告和策略效果均未读取，
组合尝试消耗仍为0，生产授权为 `none`。

## 关键边界

- 唯一处理路径为封存 `clean_lgbm_control_v1` 分数进入确定性 Head30 等权全目标转换器。
- 基线 `Top30/n_drop3` 不重跑，只在未来获批后从封存报告读取为诊断对照。
- runner 单次启动内部完成 `first_pass/replay`，两份规范化 bundle 必须物理一致。
- auditor 为第二进程，不挂载 Qlib/M6 effect，且不导入主执行、主指标或 runner 模块。
- 首次获批开始处理效果读取才写入一次尝试标记；同 scope 失败后不得重跑。
- Docker 断网、只读根、非 root、cap-drop、无 `.env`、无 Docker socket、无生产账本或完整项目挂载。

## 工程质量

- `production_conversion` 新模块共约1,400行，最大单文件261行；执行、输入、指标、审计、发布和
  合成门分层，未形成新巨型文件。
- 新 compose 纳入 `provenance.CONTROLLED_FILES`，并由 Dockerfile 显式复制进入不可变镜像。
- 镜像内首轮合成门曾因权威M6审计文档未进入旧通用镜像而失败关闭；真实效果读取0、尝试0。
  已将该唯一文档加入受控文件并置于依赖安装层之后复制，既补齐运行身份，又不扩大docs边界。
- 合成 fixture 双跑物理一致，独立审计重建结果一致，不读取真实效果、不消耗尝试。

## 验证

- Head30专项：13 PASS。
- 架构宪法：13 PASS。
- 全仓：1511 PASS，17条既有第三方/兼容性 warning。
- Ruff、compileall、Compose config、`git diff --check`、敏感凭据模式扫描：PASS。

## 尚未完成

不可变镜像构建、镜像内合成复跑和精确 release scope 尚待本实现先提交并推送后完成。完成后必须
停止在用户绑定精确 scope SHA-256 的授权前；本验收不支持任何策略有效或生产可用结论。
