# Web 模拟组合双账户切换验收

> 验收日期：2026-07-27（Asia/Shanghai）
>
> 协议：`p3-web-paper-accounts-v1`
>
> 结论：`GO_LOCAL_READ_ONLY_REVIEW`

## 1. 冻结与交付边界

展示协议和机器配置已由提交 `c5f796d` 独立冻结并先行推送，随后才修改查询层与页面。本目标只为本机
只读 Web 增加 `model_baseline` / `model_top20` 严格账户切换；没有修改模型、信号、调仓规则、研究
门槛、账本、生产数据、scheduler 镜像或 release，也没有启用 Top20 生产自动日更。

`model_baseline` 继续是默认“主账户 · Top30”，总览和股票池/信号页继续使用该账户。`model_top20`
只称为“比较账户 · Top20”，不称为新模型，不授权策略有效性或生产接入。

## 2. 接入前数据质量审计

两账户均通过独立只读重放与同粒度审计：

| 项目 | Top30 | Top20 |
| --- | ---: | ---: |
| 账户身份行 | 1 | 1 |
| PASS 账户日 | 6 | 6 |
| 事件 | 198 | 160 |
| 订单 / 成交 | 30 / 22 | 20 / 18 |
| BACKFILL / FORWARD | 4 / 2 | 6 / 0 |
| 重放 | PASS | PASS |
| `.BJ` 事件 | 0 | 0 |

两侧账户日都严格为 `20260717 / 20 / 21 / 22 / 23 / 24`；账户日键、事件 ID、账户/策略身份和不可变
产物 SHA-256 全部闭合。共享账户/事件/运行账本 SHA-256 分别为
`6dd76713...c9c5b`、`97fbce74...ccd1`、`fd0a09a5...b517f`。

观察类型不一致是已证实限制，不是可忽略缺口：Top30 有2日自然 FORWARD，Top20为0。因此只允许
切换后查看各自证据，当前禁止同图收益比较、胜负、风险改善或有效性结论。

## 3. 查询层结果

四个端点新增同名 `account_id` 参数：

- `/api/v1/paper/portfolio`
- `/api/v1/paper/nav`
- `/api/v1/paper/forward`
- `/api/v1/paper/replay`

参数只接受 `model_baseline` 和 `model_top20`，未知值返回 HTTP 422。默认值仍为
`model_baseline`，因此原调用行为保持不变；`snapshot_id` 显式绑定账户身份，四端点必须同账户、同
快照、同 `as_of`，前端也会再次核对。

零 FORWARD 现在使用完整、可验证的空态：`NOT_READY`、0观察、空序列、无锚点、无最新值，并显式
保留被压制的年化收益、年化波动、Sharpe 和信息比率字段名。后端不会为填满 schema 伪造锚点或0值。

真实本机接口终验：

- Top30：portfolio/replay PASS，nav/forward PASS，FORWARD 2，四响应同快照；
- Top20：portfolio/replay PASS，nav/forward NOT_READY，FORWARD 0，四响应同快照。

## 4. 页面结果

模拟组合页新增“主账户 · Top30 / 比较账户 · Top20”双项选择器，Top30仍为默认。切换时不保留旧账户
占位数字，必须重新取得所选账户的四个同快照响应后再渲染。

Top20 主视图常驻显示：

- 独立比较账户、目标20只；
- 当前只完成工程回放；
- 自然前瞻0日；
- 生产自动日更未启用；
- 当前不能与 Top30 比较策略优劣。

Top20 不显示前瞻图、年化收益、Sharpe 或信息比率；精确回放账户日、当前实际持仓、现金、费用、
重放摘要和技术证据仍可查看。总览、信号与其他六页的业务口径不随本页账户选择改变。

## 5. 验证

- Python Web 专项：10 PASS；真实两账户本机 API 四端点均 PASS。
- 全仓 `make test`：349 PASS，仅1条既有 Starlette/httpx 弃用 warning。
- Ruff、compileall、pip check、`git diff --check`：PASS。
- TypeScript + Vite Docker 生产构建：PASS；前端单元 24 PASS。
- 五视口 fixture Playwright：64 PASS / 11 条条件跳过；覆盖 1440/1024/768/390/320、账户切换、
  axe 与页面级回流。
- 真实本机桌面/移动 Playwright：14 PASS；覆盖 Top20 真实接口、切换、CSP、同源、axe、回流和
  FCP，确认无误导性绩效指标。

## 6. Docker 与安全终验

- 终版 Web 镜像：`sha256:fa45aa76b3eec2ee3836a2bdf1345317d3ba06553a8a95ab1c888971b82e0ba7`。
- `web-query`：`bd81299c70fe`，healthy；无宿主端口。
- `web-ui`：`74fbc17f392c`，healthy；仅 `127.0.0.1:8080`。
- scheduler 仍为 `fd8e96152b53` / `shaiwei:scheduler-current` / 2026-07-24 20:25:27 +0800，
  healthy 且未重建、未重启。

未读取或输出 `.env`，未新增凭据、Webhook、签名、原始日志或宿主绝对路径；Web 仍只读取既有只读
挂载。Docker 身份复核只使用定向非敏感字段，没有再次请求完整 inspect。

## 7. 残余边界

1. Top20 生产自动日更仍受凭据轮换和安全发布窗口阻断；Web GO 不解除该阻断。
2. 当前不启用 Top30/Top20 同图比较。待两账户形成日期匹配的自然 FORWARD 后，须另立协议并在看
   结果前冻结最小观察门槛。
3. Top20 六日回放数值只证明工程、持仓和会计可复算，不构成策略效果。
