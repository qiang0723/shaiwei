# M6-3C-R2 Top30 兼容诊断编排恢复 release 验收

- 验收时间：2026-08-07 16:00（UTC+8）
- 裁决：`GO_RELEASE_READY_NOT_EXECUTION_APPROVAL`
- 诊断分类：`NOT_EVALUATED`
- 策略有效性：`NOT_EVALUATED_FOR_PRODUCTION`
- 生产授权：`none`

## 1. 交付结论

R2 已在不改写 R1 失败证据的前提下修复容器编排门，并形成新的内容寻址 release：

- scope SHA-256：`f4ade91b9cd93f4bc248138eb3b06f5283361c7642c4b497bcfc70414422d13e`；
- scope 文件 SHA-256：`ac46f9cd642b45f16d828b7a8e10b57210982a0925df8751e49c743e0f2d9d99`；
- 协议 SHA-256：`dc38196b92b6d39c3271eae978d5931ec281e6d4d4ae21ebb2414cbb9d8337af`；
- scope 真身：`config/m6_csi800_top30_compatibility_diagnostic_recovery_scope_v2.json`。

approval 和正式输出根均不存在；真实 Qlib、封存日报、Top30 诊断和 Top20 读取/执行仍为 0。

## 2. 单变量恢复与架构

旧 `compose.m6-top30-diagnostic.yaml`及 R1 scope 文件哈希保持不变。R2 使用独立 Compose、Dockerfile、
镜像名、approval 路径和输出根；三项 tmpfs 经 YAML 和 Docker Compose v5.3.0 展开后均为一个完整
字符串，不再把 `mode=1777`解释成路径。

核心 Top30 输入验证、回测、逐位编码、分类与独立审计仍只有 R1 的一份实现。共享 runner/auditor 只
增加版本化 loader/runtime verifier 注入；R2 薄入口负责恢复合同和编排。新增实现文件最大 311 行，
没有复制第二套回测或分类逻辑。

为保证两套旧 base 镜像可移植，R2 将冻结的 R1 协议显式只读挂载到`/inputs/base-protocol.yaml`；
scope 同时绑定 recovery/base 两份协议哈希。fixture 服务保持零挂载。

## 3. 正式镜像与运行门

- 实现 Git：`9c36088f26eb152ecb580efc982fe5b9425935e3`；
- 代码 bundle：`a8c4e687b7042a6155906df34ae2f31cbdabf9f9e8ead24831a0595ba84c6201`；
- Compose SHA-256：`54c3e5a2cf880cc20858c270066e9c05257f16c900a7beb170b800740ca18358`；
- Dockerfile SHA-256：`a60bea8abc2590437891354745385ffc1be25c1168ba15b71b5f6026b521f810`；
- original 镜像：`sha256:395c0134ba83c080f0327eb96e94157c49ac6816ae95c2c2ab153c8f4422d58e`；
- current 镜像：`sha256:51dda65481c452ffa0a8fe63b0eb2a3c2f4619897d2a56f239dc41cabaab902a`；
- original/current 镜像清单 SHA-256：`765aeaba...3e98` / `0571c466...fa93`；
- 两套平台均为`linux/arm64`，base 镜像仍分别是原 M6 `3c40c9c...cd40e`和失败 M6-3C
  `69c1a497...afa17`。

两套镜像均在断网、非 root、只读根、仅配置挂载下完成 scope、自哈希、Git、代码 bundle、base 和
镜像清单复核。三项 Compose fixture 都实际创建并退出成功：有效 UID 501、IPv4 路由 0、tmpfs 可写、
真实输入挂载 0、六类合成分类 PASS、外部调用 0。

## 4. provisional 留痕

所有问题均在新 scope 获批和真实读取前发现并停止：

1. 首批镜像成功证明 tmpfs 容器可创建，但 fixture 错把 Docker Desktop 隔离命名空间中的内核虚拟
   接口视为外网，original/current ID 为`86a2d736...a4ff`/`e1fbc85b...ff93`。判据改为无 IPv4 路由；
2. 第二批构建手工补全短 Git 错误，ID 为`5edd9bcd...619e`/`36520690...32f9`；在 scope 前由完整
   `git rev-parse`复核拦截；
3. 第三批镜像 fixture PASS，但配置级运行身份发现 base 镜像内没有后建 R1 协议；ID 为
   `ba3fdee6...a4e0`/`cb2d0c87...902a`。对应 provisional scope 为`2b040fb8...934c`，文件 SHA-256
   `7a36aa8a...cb4c`，已保存在 Git 忽略区；随后改为显式只读挂载 base protocol。

三批均未创建 approval、未挂真实 Qlib/effect、未运行 Top30/Top20、未写实验账本，不能用于正式执行。

## 5. 验证与生产隔离

- 全仓测试：929 PASS，只有 1 条既有 Starlette 第三方弃用提示；
- R1+R2 专项：11 PASS；架构门：10 PASS；
- Ruff、compileall、pip check、Compose 展开、YAML/JSON、自哈希、`git diff --check`和脱敏检查：PASS；
- scheduler 保持原容器`183b8c6c...23dd3b`、原镜像`722f63de...13b76`、`healthy`、重启 0；
- 7 个 scheduler 自然账本改动未暂存，R2 无一次性容器残留。

## 6. 精确授权门

后续若继续，用户必须逐字批准动作：

`M6_TOP30_COMPATIBILITY_DIAGNOSTIC_MATRIX_RECOVERY_ONCE`

并绑定完整 scope SHA：

`f4ade91b9cd93f4bc248138eb3b06f5283361c7642c4b497bcfc70414422d13e`

获批后也只能各运行一次 R2 original runner、current runner 和独立 auditor；任何阶段失败不得在同
scope 重跑。诊断成功只形成工程根因分类，不授权 Top20、模型、前瞻、模拟仓或生产。
