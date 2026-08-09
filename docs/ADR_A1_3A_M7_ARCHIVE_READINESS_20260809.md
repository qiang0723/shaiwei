# A1-3A M7 归档就绪 ADR（2026-08-09）

## 裁决

`LOCAL_ARCHIVE_REHEARSAL_PASS_REMOTE_DURABILITY_NOT_READY`。

M7 的代码恢复锚点和本机恢复材料已经建立，本机断网恢复演练通过；但镜像与 Git 忽略的真实执行证据尚无
异机副本，也未在全新 Docker 引擎或另一台主机恢复。因此这不是灾备 PASS，不授权 A1-3B，不删除任何
源码、测试、构建文件、配置、证据或数据。

## 本次建立的恢复锚点

1. annotated tag `m7-moneyflow-recovery-final-20260809` 已推送到 `origin`，只指向 M7 终局提交
   `49e9d740e3ed44121e14047c338212913b7798c7`。该 tag 禁止移动；未来纠错只能建立 successor tag。
2. 冻结 arm64 镜像 `sha256:5b15e23f...b3da` 已导出到项目内 Git 忽略目录
   `data/archive/m7-moneyflow-recovery-final-20260809/images/`。tar 为只读，SHA-256 为
   `d4f8e1e7913a557ad6d68fdc5862fd4b1d2b2dcfd7591ce817310e1e5ae2546d`，共 165,929,984 bytes。
3. tar 可被当前 Docker 引擎重新 load，得到完全相同 image ID。冻结镜像随后在 `network=none`、只读根、
   无项目挂载、drop all capabilities、no-new-privileges 条件下运行自带 synthetic fixture，结果 PASS；
   外网、真实密钥和项目数据读取均为 0。
4. 既有 M7 终局执行目录复核为 3,480 文件、237,604,601 bytes；报告、双 manifest 和独立审计 SHA-256
   均与终局验收一致。没有重跑 provider、evaluator、auditor，也没有读取资金流数值形成新研究结果。

机器真身见 `config/a1_3a_m7_archive_readiness_v1.json`。

## 为什么仍不允许清理

- Git tag 只能恢复代码，不能恢复当前未提交的镜像 tar 和 Git 忽略业务证据。
- tar 和真实执行证据仍与项目处于同一台 Mac、同一块本地存储；本机磁盘损失会同时失去两者。
- 本次 `docker load` 在当前引擎完成，只证明归档格式可读，不等于从零、异机灾备恢复。
- `RepoDigest` 为本机内容身份，不等于镜像已经存在于可拉取的私有 registry。
- M7 冻结 v1 中已登记的旧半年度 `segment` 校验误报必须原样保存，不能以归档名义静默修复。

因此 `SAFE_DELETE_NOW=[]`，A1-2 估算的 105 文件/14,660 行仍只是归档后逐文件评审上界，不是删除清单。

## 后续解锁条件

A1-3B 之前至少要完成以下条件，并由用户再次批准精确文件清单：

1. 把冻结镜像保存到已验证可拉取的私有 registry，或用户指定的异机只读备份位置；
2. 把 M7 终局 Git 忽略证据及其 hash manifest 保存到异机位置；
3. 在全新 Docker 引擎或另一台主机按 tag、镜像和证据 manifest 完成一次恢复复核；
4. 对 105 个候选文件逐项证明无活跃消费者、无唯一复算职责，并永久保留协议、裁决、manifest 和 ADR；
5. 用户对最终精确删除清单重新授权。

在远程服务器或私有 registry 目的地未确定前，本地归档保持只读，不把“有一份本地 tar”误报成灾备完成。

## 生产与安全边界

生产 scheduler 始终为容器 `183b8c6c5edd`、镜像
`sha256:722f63de...13b76`、状态 healthy，未重启。归档未挂载生产数据、未访问项目外目录、未读取或提交
`.env`，未暂存七个自然运行账本，Git 中不新增原始/派生业务数据或凭据。
