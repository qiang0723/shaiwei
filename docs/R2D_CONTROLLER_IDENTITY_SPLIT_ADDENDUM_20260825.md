# R2D 宿主控制器与候选运行时身份分离勘误

R2C-R1 候选在 R2D 发布控制器施工前已经构建并通过唯一 fixture。R2D 又必须新增宿主侧 prepare/start
控制逻辑，因此“最终仓库受控快照等于候选镜像快照”无法成立；若为追求相等而重建候选，就必须重做
已关闭 fixture scope，反而破坏原证据链。

本勘误把身份分成两条，均须精确绑定：

1. **候选运行时身份**保持不变：HEAD `55f98e7`、snapshot `88e3f471...abec0`、image ID
   `b7565001...baa72`及R2C-R1全部fixture哈希继续是生产运行真身，不重建、不重跑。
2. **宿主发布控制器身份**在工程完成后单独绑定最终 HEAD 和组件SHA。允许的源码变化仅限
   `release_build_context.py`、`release_guard.py`、`daily_early_release_guard.py`和新增
   `r2d_release_guard.py`，以及对应测试、R2D配置和文档。

必须有机器门证明候选 HEAD 到最终控制器 HEAD 的受控差异未触碰 Dockerfile、Compose、settings、
scheduler/daily/shadow/paper、模型、信号或门禁运行路径。执行 scope 原要求
`current_controlled_code_snapshot_equals_candidate_snapshot`由“候选身份和fixture不变 + 宿主控制器HEAD/
组件SHA精确 + 差异允许清单PASS”替代。

这是发布控制面与运行数据面的正常身份分离，不是降低快照门。勘误仍在实现提交和任何Docker/生产动作
之前完成，不授权build、fixture、promote、restart、业务读取或真实账本写入。

