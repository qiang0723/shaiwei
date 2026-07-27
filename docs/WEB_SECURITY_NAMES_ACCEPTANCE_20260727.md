# Web 模拟仓中文简称展示验收

> 日期：2026-07-27（Asia/Shanghai）
>
> 协议：`p3-web-security-names-v1`
>
> 结论：`GO_LOCAL_READ_ONLY`

## 交付结论

模拟组合“实际持仓”首列已显示中文简称，股票代码保留在同一单元格第二行作为审计标识。名称只用于
可读性，没有改变账户、模型、信号、排序、交易、估值、门禁或判决；页面仍只开放本机只读访问。

## 数据与证据

- PIT 主源 `tushare.namechange`：13,448条历史、5,428只证券；重复历史区间0。
- 当前简称兜底 `tushare.stock_basic`：5,535只沪深证券；`T600018.SH` 为交易所测试证券，排除并计数1。
- 内容寻址 bundle SHA-256：`9651c35bcfdba59ca934cd7e69134e2ced8a5ea539ac9def7a65901c6fa8fc75`。
- `current.json` SHA-256：`90ee0b299cd6ebb580b07a482c986029fd9d063905997e1de4beca464b5f6688`。
- 相同 Docker 入口二次运行后两个哈希均不变。
- Top30 最新账户日：22/22个持仓名称为 `NAMECHANGE_PIT`；fallback 0、missing 0、`.BJ` 0。
- Top20 最新账户日：18/18个持仓名称为 `NAMECHANGE_PIT`；fallback 0、missing 0、`.BJ` 0。
- 两账户合计40个持仓行、24只不同证券，名称覆盖40/40。

原始 Parquet 没有挂载到常驻 Web，也没有进入 Git。断网投影器不读 `.env`、不访问网络；Web snapshot
同时绑定名称指针、bundle和源身份，篡改、指针错配、未知代码或歧义名称均失败关闭。

## 验证

- Python 名称/查询专项：14 PASS。
- 全仓：355 PASS；仅1条既有 Starlette 弃用提示。
- Ruff、`git diff --check`：PASS。
- 前端单元：25 PASS。
- TypeScript与Vite生产构建：PASS。
- 真实本机HTTP：两个账户均返回200，名称覆盖状态均PASS。
- 已部署 `PaperPage` 静态分块包含“中文简称 / 代码”、缺失名称空态和PIT来源分支。

终版 Web 镜像为
`sha256:0998e8ea67b28e3332780633a062d9303cbba195b70239aa86bdcc7d1a759e8a`；`web-query`
与 `web-ui` 均 healthy。scheduler 发布前后均为容器 `fd8e96152b53`、镜像 `de87ec740981`、创建时间
`2026-07-24 20:25:27 +0800`，保持 healthy 且未重启。

## 剩余边界

本次未新增浏览器自动化镜像，既有 E2E fixture 已更新但未在本轮重新执行全视口 Playwright；真实API、
生产构建和已部署静态分块已验证。未来 `namechange/stock_basic` 登记源发生变化时，先运行
`make docker-web-security-names-project` 生成新内容寻址投影，再显式更新 Web；不接入 scheduler。
