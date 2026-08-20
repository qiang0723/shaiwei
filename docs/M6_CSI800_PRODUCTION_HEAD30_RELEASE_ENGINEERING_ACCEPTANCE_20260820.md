# M6-4B 生产 Head30 转换器发布工程验收

## 结论

`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`。一次性真实 runner、内部 replay、独立 auditor、不可变
产物合同、隔离 Docker、不可变镜像和精确 release scope 均已完成；真实 Qlib、封存预测值、控制
报告内容和策略效果均未读取，组合尝试消耗仍为0，生产授权为 `none`。

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
  第二轮构建又由既有`docs/*`上下文规则正确阻断；现已为该文件增加单项白名单，不开放其他docs。
- 首次scope生成在写入前因相对审计路径未规范化而失败关闭；已改为先解析、再强制验证输入仍位于
  项目目录内，避免工作目录差异和越界路径。该失败同样没有写scope、读取效果值或消耗尝试。
- 终版全仓回归发现旧M7测试把历史发布身份与当前工作树捆绑；M6新增Docker单项白名单会使已关闭
  的M7发布被追溯判失效。现改为核对M7冻结时的历史bundle哈希，同时保留当前bundle确定性测试；
  未改旧scope、旧产物或任何运行权限。
- 合成 fixture 双跑物理一致，独立审计重建结果一致，不读取真实效果、不消耗尝试。

## 不可变发布身份

- 实现提交：`27fdd6cb00962bea5d129005d24208f0724b4b78`，构建时已与`origin/main`一致。
- 镜像：`shaiwei:m6-production-head30-release-v1`，ID
  `sha256:67beb7ea55c2b1a096a61be165f414a9403c9e0e81ad07785c6e554a44cca81d`，平台
  `linux/arm64`。
- 镜像代码快照：`0eda1be6ea2538fa49c40e2cf0d3c9b645ecf59bd7e4d323b5371804bc008683`；
  与构建前宿主受控快照一致。
- 镜像清单：1,117个受控文件，清单SHA-256
  `fbb58f13566141369b006d6c14e2d78cdf89b52c1be2ebc349b001080e4d3e85`。
- 精确release scope：`config/m6_csi800_production_head30_release_scope_v1.json`，scope SHA-256
  `15b3c7854409adb6d9f32f74f583a156088513d17520f43e8df61d04321143b3`，文档SHA-256
  `561346e3655b6ce664ae54990b3534af08cdaa63e0315b76dad40deb6b9cb14a`。
- 镜像内合成fixture：first/replay均为
  `269ce579532e8115dd55f17d4d65313e5976765a3e624f12e20126a9552ca301`；独立重建PASS；
  report SHA-256 `e6b097ff777025fafa40cae23050733d17061f1c9ce12abae1042b23525121af`。

## 验证

- Head30专项：14 PASS。
- 架构宪法：13 PASS。
- 全仓：1512 PASS，17条既有第三方/兼容性 warning。
- Ruff、compileall、Compose config、`git diff --check`、敏感凭据模式扫描：PASS。

## 尚未完成

真实效果运行尚未发生。必须停止在用户绑定上述精确scope SHA-256的授权前；本验收不支持任何
策略有效、模拟仓可用或生产可用结论。同scope运行失败后不得重跑，任何恢复都必须另立协议与scope。
