# R2-1H0 Mac 宿主连续运行验收

- 验收时间：2026-08-24T15:15:53+08:00
- 依据：`docs/ADR_005_MAC_HOST_AVAILABILITY_20260824.md`
- 裁决：`GO_POWER_POLICY_VERIFIED / LOGIN_AUTOSTART_CONFIRMATION_PENDING`
- scheduler 发布授权：无

## 1. 用户授权与执行

用户明确回复“批准执行”后，仅执行 ADR-005 冻结的 AC Power 系统睡眠变更：

```text
sudo pmset -c sleep 0
```

首次终端式 sudo 因需要管理员密码而被立即中止，未发生修改；没有要求用户在对话中提供密码。随后使用
macOS 原生管理员认证弹窗执行同一条精确命令，用户凭据未经过 Codex、项目文件、日志或 Git。

## 2. 只读复核

变更后 `pmset -g custom`：

- AC Power `sleep=0`：PASS；
- AC Power `displaysleep=5`：PASS，熄屏策略未改；
- `powernap=1`、`womp=1`、`ttyskeepawake=1`、`disksleep=10`：与变更前一致；
- 只使用 `-c`，未修改电池模式、VPN、代理、Codex 或其他应用。

Docker 只读复核：

- 容器：`183b8c6c5eddac951d9d9b3cfa58c0d38e351d5b94ee1b1d52b9b8059c23dd3b`；
- 镜像：`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`；
- 启动时间：`2026-08-03T09:39:38.242399128Z`；
- 状态：`running / healthy`；
- RestartPolicy：`unless-stopped`。

容器、镜像、启动时间与重启策略均未变化；本节点未 build、promote、restart 或运行真实业务周期。

## 3. 剩余人工确认

Docker Desktop 是否配置为“登录时启动”不从项目外配置文件读取，仍需用户在 Docker Desktop 设置内人工
确认。该项只影响 Mac 重启后的 daemon 自动恢复，不影响当前已运行且 healthy 的 scheduler。

在人工确认完成前，不进入 scheduler timeline 真实发布。确认后另立不可变 release，避开
16:00—19:30 数据窗口；本次不回填历史时间线。

## 4. 回滚

若用户以后决定恢复本次变更前的 AC Power 原值，需另行批准：

```text
sudo pmset -c sleep 1
```
