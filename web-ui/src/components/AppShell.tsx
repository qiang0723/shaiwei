import {
  ApartmentOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FundProjectionScreenOutlined,
  MenuOutlined,
  ReadOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StockOutlined
} from "@ant-design/icons";
import { Button, Drawer, Tooltip } from "antd";
import { useMemo, useState, type ReactNode } from "react";
import { RouterLink, useRouter } from "../routing";

const primary = [
  { path: "/overview", label: "总览", short: "总览", icon: <FundProjectionScreenOutlined /> },
  { path: "/paper", label: "模拟组合", short: "组合", icon: <BarChartOutlined /> },
  { path: "/signals", label: "股票池 / 信号", short: "信号", icon: <StockOutlined /> }
];

const operations = [
  { path: "/data-quality", label: "数据质量", short: "数据", icon: <DatabaseOutlined /> },
  { path: "/system-runs", label: "系统运行", short: "运行", icon: <SettingOutlined /> }
];

const deferred = [
  { label: "因子工厂", icon: <ExperimentOutlined /> },
  { label: "模型 / 回测", icon: <ApartmentOutlined /> }
];

const mobile = [...primary, ...operations];

export function useAsOf() {
  const { location, navigate } = useRouter();
  const asOf = useMemo(() => new URLSearchParams(location.search).get("as_of") ?? "", [location.search]);
  const setAsOf = (value: string) => {
    const query = value ? `?as_of=${encodeURIComponent(value)}` : "";
    navigate(`${location.pathname}${query}`);
  };
  const link = (path: string) => `${path}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
  return { asOf, setAsOf, link };
}

function Navigation({ close }: { close?: () => void }) {
  const { location } = useRouter();
  const { link } = useAsOf();
  return (
    <nav aria-label="主导航" className="sidebar-nav">
      <div className="nav-group-label">决策工作台</div>
      {primary.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={location.pathname === item.path ? "nav-item active" : "nav-item"}
          aria-current={location.pathname === item.path ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
      <div className="nav-group-label deferred-label">运行与证据</div>
      {operations.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={location.pathname === item.path ? "nav-item active" : "nav-item"}
          aria-current={location.pathname === item.path ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
      <div className="nav-group-label deferred-label">后续只读能力</div>
      {deferred.map((item) => (
        <Tooltip title="查询契约尚未开放" placement="right" key={item.label}>
          <span className="nav-item disabled" aria-disabled="true">
            {item.icon}
            <span>{item.label}</span>
            <small>待接入</small>
          </span>
        </Tooltip>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileMenu, setMobileMenu] = useState(false);
  const { asOf, setAsOf, link } = useAsOf();
  const { location } = useRouter();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主内容
      </a>
      <aside className="app-sidebar">
        <RouterLink className="brand" to={link("/overview")} aria-label="筛微总览">
          <span className="brand-mark">筛</span>
          <span>
            <strong>筛微</strong>
            <small>Evidence first</small>
          </span>
        </RouterLink>
        <Navigation />
        <div className="sidebar-boundary">
          <SafetyCertificateOutlined />
          <span>
            本机只读
            <small>不连接券商 · 不可改参</small>
          </span>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="topbar">
          <Button
            className="mobile-menu-button"
            type="text"
            icon={<MenuOutlined />}
            aria-label="打开导航"
            onClick={() => setMobileMenu(true)}
          />
          <div className="topbar-context">
            <ReadOutlined aria-hidden="true" />
            <span>量化研究决策台</span>
            <span className="readonly-pill">READ ONLY</span>
          </div>
          <div className="asof-control">
            <label htmlFor="as-of-date">证据日期</label>
            <input
              id="as-of-date"
              type="date"
              value={asOf}
              aria-label="证据日期，留空表示最新"
              onChange={(event) => setAsOf(event.target.value)}
            />
            {asOf ? (
              <Button type="link" size="small" onClick={() => setAsOf("")}>
                查看最新
              </Button>
            ) : null}
          </div>
        </header>

        <main id="main-content" className="app-content" tabIndex={-1}>
          {children}
        </main>

        <nav className="mobile-bottom-nav" aria-label="移动端主导航">
          {mobile.map((item) => (
            <RouterLink
              key={item.path}
              to={link(item.path)}
              className={location.pathname === item.path ? "active" : ""}
              aria-current={location.pathname === item.path ? "page" : undefined}
            >
              {item.icon}
              <span>{item.short}</span>
            </RouterLink>
          ))}
        </nav>
      </div>

      <Drawer
        className="mobile-navigation-drawer"
        title="筛微 · 只读决策台"
        placement="left"
        open={mobileMenu}
        onClose={() => setMobileMenu(false)}
        width="min(320px, 88vw)"
      >
        <Navigation close={() => setMobileMenu(false)} />
      </Drawer>
    </div>
  );
}
