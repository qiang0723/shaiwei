# R2D-R3G：20260908自然闭环后的start-only冻结

状态：ENGINEERING_FROZEN / PREFLIGHT_NOT_AUTHORIZED / PRODUCTION_NOT_AUTHORIZED。

## 结果与来源

2026-09-09 09:12:36 UTC+8，用户批准的单次只读补验完整结束：20260908 daily=1、
shadow=1、paper=2，均PASS；双账户最新PASS均为20260908，operator=docker-scheduler、
freshness=PASS，实际产物SHA、FORWARD mode和九项身份均匹配账本。
这只证明获准的元数据门，不等于重新执行paper-verify、通知验收或策略效果评价。

release current仍为候选97d8c05e...7553 / b64ae11...5ebe，previous仍为旧生产。
state SHA为`c879228f6514b3a07c0d1a6efec0c68832d0feab7444821e9376de1bfd86c454`；
audit SHA为`4524d2d0af6d57dbf1fad6c57dcb623f62eb39f63930d278c26999f895e1eea1`。
audit 34条、链PASS，末事件PROMOTE_PASS（2026-09-03T12:53:26.697482+00:00），
末记录SHA为`aca0245b0e59e19612a2fd332dcb10188f0cfbfcd4eb5211f1167587819f477d`。

health为noop / 20260908，updated_at=2026-09-09T01:03:50.519203+00:00。
该上午心跳不满足下午16:00后门；本次未核验20260909目标账本、实时Docker或readiness。

## 新冻结配置

配置：`config/r2d_scheduler_release_guard_r3g_start_v1.yaml`。
文件SHA-256：`4dfb9171c1b800057c9f059a675a66d9908f323bdf3d3e52539d59f768221db1`。

继承R3F的候选、previous、四挂载、R3A封存fixture和13组件控制器，全部身份不变。
controller_source_head仍为69f0d913ebd60126ebe8d2f190053329858a45d6，组件SHA仍为
f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998。
不重建候选、不重跑fixture，不修改旧R3F配置、历史回执或门槛。

本次只推进自然日期及最新FORWARD绑定：

- target_trade_date=20260909，start_window为Asia/Shanghai 16:40（含）—19:00（不含）；
- legacy boundary为20260909当天16:00后自然形成的noop / 20260908；
- 20260909 daily/shadow/paper所有尝试（含失败或部分尝试）计数必须均为0；
- 最新model_baseline与model_top20必须仍是20260908的PASS/FORWARD，代码均为旧生产
  4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708；
- Top30产物SHA：9ef872c17c4fea2ee277029ea930dad739f0709544f4c82d9f69f047bae30312；
- Top20产物SHA：0faa96dad0f8352bb30a96ac450541562d6607abbead80332f6b22c5c8ea805d。

Phase A已完成，prepare入口必须失败关闭。19:00后不补做、不顺延或复用scope。

## 日历与Compose身份

独立日历：
`data/control/r2d-calendar-evidence/c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114/day.txt`。
每次使用必须校验SHA=c9916944c6865cf4e1e6b15af7ac90a54d2275320d25353873071f08d892b114。
本次09:12补验确认哈希匹配、日期有序唯一、20260908后首个交易日20260909。
不回读已被清理的旧qlib路径；副本保留背景见日历恢复记录。此文件仅支持日期证据，
不能替代release_metadata.load_plan从获准的trade_cal元数据运行权威readiness规划器。

20260908晚间定向Docker观察的Compose project为`shaiwei_init`；预期旧容器ID为
`7a55151d4d5d686b01fbf26c76432754302358b2faa653eac21ca07ee78780c4`。
未来scope必须填此项目值，且在同一精确旧容器上再次核验project标签。
禁止猜测project=shaiwei、扫描其他项目、修改Compose project来绕过门。
重启数必须为0、healthy、只读根及三个项目bind加shaiwei_runtime_locks_v1四挂载符合合同。

现有ExecutionScope直接绑定compose_project、旧容器ID和YAML全文/哈希；独立日历校验属于
scope生成前的显式操作人核验，并非新增了执行Schema字段或声称执行器已自动验证日历副本。
现有readiness、身份、时效、原子单次消费、派发后禁止自动回滚合同继续适用。

## 交付与后续授权

工程范围仅新配置、合成协议测试、本文、STATE及ROADMAP。验证结果见下方验证记录。
不读取新的生产数据，不生成真实scope/批准文件/claim/barrier/receipt，无Docker、外网或生产动作。

本地origin/main在开工时仍为69f0d91，虽8268f28已有直接URL推送成功回执，不能据此伪造或静默
更新跟踪引用。终版推送需覆盖本地日历文档提交8ed84fe及本次R3G提交，并获现有仓库明确网络授权；
随后定向同步origin/main，核实HEAD和引用相等，不将本地跟踪值冒充实时远端状态。

工程交付后，唯一下一节点为单独授权的20260909窗口内一次scope生成和无--execute预检。
读取清单必须明确覆盖R3A封存证据、13组件、控制器Git、本地引用、release/audit、health、
目标日三类计数、最新双账户身份及产物哈希、独立日历、权威readiness所需trade_cal元数据和定向
Docker字段。通过后才以不可覆盖方式写一份scope，并运行一次无--execute预检。
任一失败或跨窗口即停止、不重试；没有写入scope时如实报告，不伪称已消费执行claim。
预检PASS后报告scope全文身份摘要、哈希和精确批准文本，等待独立start授权。

真正start调用仍涉及Compose部署凭据、容器内健康检查及生产常驻进程；这些不属于本工程或
无密钥只读预检授权。生产授权必须明确这些实际调用边界，不可沿用禁止Compose/docker exec/
凭据读取的只读授权启动。派发后禁止自动回滚，失败需独立人工恢复协议。

候选自然首日完整验收前R2D不关闭，G1不开工。之后顺序为G1正向对照校准、Style Attribution v1、
W7和100/300/500/1000万元梯度；R2-1R1自然累积不阻塞G1。

## 验证记录

- R3G及R2D安全合同专项76 PASS，涵盖精确窗口边界、上午/前日心跳、任一目标尝试和旧入口禁用。
- 受保护make test：2028 PASS、1 deselected、17项既有警告，238.77秒。
  唯一未执行项为真实.env密钥比对，遵守当前禁读边界，不宣称该项通过或修改常设门。
- make architecture-check：13 PASS；新测试Ruff、配置SHA及文档引用、旧R3F逐字节保持检查PASS。
- 凭据形状扫描未发现命中；它不等于真实密钥值比较。

测试使用既有r2d_safety保护器，合成文件进入本次唯一.test-tmp子目录，真实生产写入及网络被阻止。
未运行真实预检或读取新的真实效果；保留原有账本增量、校准底稿及所有历史证据。
