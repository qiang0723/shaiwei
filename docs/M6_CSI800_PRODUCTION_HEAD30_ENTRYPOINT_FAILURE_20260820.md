# M6-4B 生产 Head30 入口失败留痕

## 权威状态

原scope `15b3c7854409adb6d9f32f74f583a156088513d17520f43e8df61d04321143b3`已于
2026-08-20 14:15:03（UTC+8）调用一次，并在Docker创建容器前失败关闭。原scope不得重跑。

- Docker返回：`invalid mount path: 'noexec' mount path must be absolute`。
- Compose把`tmpfs: [/tmp:rw,noexec,nosuid,size=4g,mode=1777]`解析为五个独立挂载项；
  `docker compose config --quiet`只验证配置语法，没有验证daemon挂载语义。
- runner容器未创建；effect与audit目录均为0个文件；`treatment_effect_started.json`未写入。
- 真实Qlib、封存预测值、控制报告内容和策略效果均未读取；组合转换尝试消费0。
- scheduler保持原容器healthy，未重启；生产授权仍为`none`。

机器证据为`config/m6_csi800_production_head30_entrypoint_failure_v1.json`。后续只能另立
M6-4B-R1结果盲编排恢复协议，修复tmpfs序列化并增加daemon级容器创建fixture；不得修改原scope、
原批准记录或静默重跑。
