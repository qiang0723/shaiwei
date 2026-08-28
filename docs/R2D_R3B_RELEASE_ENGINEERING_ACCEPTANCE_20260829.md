# R2D-R3B 发布工程验收

## 裁决

`GO_RELEASE_ENGINEERING_READY / PRODUCTION_EXECUTION_NOT_AUTHORIZED`。

## 已完成

- R3A 与历史 R2C fixture 证据改为显式双格式校验；R3A 严格绑定六个 case、候选合同、生产证据不变、report/tree/receipt 哈希；
- R2D CLI 新增受控 `--protocol-path`，只接受项目 `config/` 直属、`r2d_*.yaml` 非符号链接文件；旧 v1/r1/r2 入口保持兼容；
- 控制器身份清单由四/五组件兼容扩展为四至六组件封闭集合，新证据模块进入当前六组件哈希；
- Phase A 与 Phase B 配置独立，Phase A 无 start authority，Phase B 无重复 prepare authority；
- 20260828 自然边界和 R3A 唯一 PASS 证据已绑定。

## 验证

- R3B/R2D专项：34 PASS；全仓：1,954 PASS，17条既有第三方弃用或pandas未来行为提示；
- 架构门：13 PASS；Ruff、compileall、协议模型解析、diff-check、凭据模式扫描：PASS。

## 未执行

未 promote、start、restart、重建候选、重跑 fixture、手工跑批、历史回填；未读取 `.env`/密钥，未访问外网，未修改模型、信号、策略、Web、生产数据或运行账本。

## 下一停止点

先完成全仓、架构、静态、脱敏和配置一致性验证并推送最终提交；随后仅生成 Phase A 的精确 Git 忽略 scope，请用户逐字批准。Phase B scope 只能在 Phase A 成功且 20260831 自然边界可核验后生成。
