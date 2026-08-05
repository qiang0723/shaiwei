# M5-2A 科创三池动态基本面协议冻结验收（2026-08-05）

## 裁决

`GO_M5_2A_PROTOCOL_FREEZE_ONLY`

本裁决仅证明结果前协议已提交推送并形成内容寻址 protocol scope。它不等于 DATA_GATE_APPROVED，
不授权读取真实数据、运行 synthetic 工程门、查看标签/效果、调用 provider、训练/回测、接入 Web、
前瞻、模拟仓或生产。

## 冻结身份

- protocol commit：`98f2d10b2eb76809b0bf373d0be1ebcd5d1198b6`
- parent：`15bab7accfa01f86791dd4ea31e8ebd5d80f1e6d`
- tree：`b81a70c9894b5570b3833f0eb033d8d349eae17c`
- 推送证明：scope 创建时本地 `origin/main` 与 protocol commit 相等
- protocol scope SHA-256：`ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557`
- scope envelope 物理 SHA-256：`9477b31aaa767a65f178682947ef8b62e4f2e0f6bf662cdd52359ee1c5a95ca8`

scope 同时绑定 proposal ID、request SHA、canonical proposal SHA、seq=2事件链头、proposal export、
ADR、机器配置、架构宪法、测试和远端冻结提交；物理/规范哈希均为 SHA-256。

## 冻结的研究合同

- home：`star50-official-pit-v2`；transfer：`star-board-midcap-pit-v1`、
  `star-board-smallcap-pit-v1`，后两者永久标 `CUSTOM_RULE_BASED`。
- 固定八式：毛利率改善、研发强度改善、应收占收恶化、库存积累、杠杆变化、流动比率改善、外部融资
  依赖、自由现金流率改善；三池同方向，与F2六式零重复，不补位。
- 固定8次生成尝试和24个评价单元；协议冻结后动态基本面主域`N=6→14`，基本面联合敏感性
  `N=12→20`，效果测试仍为0。
- PIT、严格连续年报、分母/负值、缺失不填、548日陈旧度、2021—2025十个半年数据段、未来六窗、
  标签成熟和三个压力期已在结果前固定。
- FULL/PARTIAL/NO-GO、候选级三池全过、无替补、相关性只诊断不折减N均已固定。

## 独立复核闭环

研究专项首轮发现并阻断：自建池过滤字段错误、半年段/未来窗口不精确、负值与陈旧度未定义、相关性
合同与PARTIAL映射缺失、测试不足。全部补正后给出 `GO_M5_2A_PROTOCOL_FREEZE`。

架构专项首轮发现并阻断：单次批准与双门冲突、protocol/release scope循环、M5-1取消语义错误、
FULL/PARTIAL混入lifecycle、stop rule批准时点含混、export交叉绑定测试不足。全部补正后给出
`GO`，范围严格为 protocol-only提交推送。

两次阻断都发生在提交和真实数据读取前；没有生成补正版本或隐藏失败证据。

## 验证

- `tests/test_m5_dynamic_fundamental_protocol.py`：10 PASS；
- 全仓：665 PASS；
- 架构门：6 PASS；
- Ruff、compileall、pip check、Git diff-check、仓库凭据/数据脱敏门：PASS；
- 唯一 warning 是既有 Starlette TestClient 第三方弃用提示；
- 协议冻结期间未调用网络数据源、DeepSeek或飞书，未读取标签/效果，未启动/重启任何服务。

生产 scheduler 复核仍为原容器 `183b8c6c5edd`、原镜像
`sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76`、创建时间
`2026-08-03 17:39:34 +0800`，状态 healthy；本目标未修改其配置、镜像、容器或挂载。

## 下一合法动作

只允许先施工并推送 M5-2B 数据门实现、短命断网镜像、输入 manifest、挂载/资源合同和独立 auditor，
再生成 `data_gate_release_scope_sha256`。用户看到并批准该精确 scope 之前：

- `data_gate_approval_recorded=false`；
- `real_data_read_authorized=false`；
- `engineering_gate_approval_recorded=false`；
- `effect_test_count=0`；
- `production_authorization=none`。
