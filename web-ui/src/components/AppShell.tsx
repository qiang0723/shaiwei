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
import { Button, Drawer } from "antd";
import { useMemo, useState, type ReactNode } from "react";
import { RouterLink, useRouter } from "../routing";

const overview = [
  { path: "/overview", label: "总览", short: "总览", icon: <FundProjectionScreenOutlined /> }
];

const research = [
  { path: "/factors", label: "因子工厂", short: "因子", icon: <ExperimentOutlined /> },
  { path: "/experiments", label: "模型 / 回测", short: "实验", icon: <ApartmentOutlined /> }
];

const decisions = [
  { path: "/paper", label: "模拟组合", short: "组合", icon: <BarChartOutlined /> },
  { path: "/signals", label: "股票池 / 信号", short: "信号", icon: <StockOutlined /> }
];

const operations = [
  { path: "/data-quality", label: "数据质量", short: "数据", icon: <DatabaseOutlined /> },
  { path: "/system-runs", label: "系统运行", short: "运行", icon: <SettingOutlined /> }
];

const mobile = [...overview, research[0]!, decisions[0]!];

function pathIsActive(current: string, target: string): boolean {
  return target === "/factors" || target === "/experiments"
    ? current.startsWith(target)
    : current === target;
}

export function useAsOf() {
  const { location, navigate } = useRouter();
  const asOf = useMemo(() => new URLSearchParams(location.search).get("as_of") ?? "", [location.search]);
  const setAsOf = (value: string) => {
    const parameters = new URLSearchParams(location.search);
    if (value) parameters.set("as_of", value);
    else parameters.delete("as_of");
    const query = parameters.size ? `?${parameters.toString()}` : "";
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
      <div className="nav-group-label">今日</div>
      {overview.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={pathIsActive(location.pathname, item.path) ? "nav-item active" : "nav-item"}
          aria-current={pathIsActive(location.pathname, item.path) ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
      <div className="nav-group-label deferred-label">研究证据</div>
      {research.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={pathIsActive(location.pathname, item.path) ? "nav-item active" : "nav-item"}
          aria-current={pathIsActive(location.pathname, item.path) ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
      <div className="nav-group-label deferred-label">组合与执行</div>
      {decisions.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={pathIsActive(location.pathname, item.path) ? "nav-item active" : "nav-item"}
          aria-current={pathIsActive(location.pathname, item.path) ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
      <div className="nav-group-label deferred-label">数据与运行</div>
      {operations.map((item) => (
        <RouterLink
          key={item.path}
          to={link(item.path)}
          onClick={close}
          className={pathIsActive(location.pathname, item.path) ? "nav-item active" : "nav-item"}
          aria-current={pathIsActive(location.pathname, item.path) ? "page" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </RouterLink>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileMenu, setMobileMenu] = useState(false);
  const { asOf, setAsOf, link } = useAsOf();
  const { location } = useRouter();
  const researchContext =
    location.pathname.startsWith("/factors") || location.pathname.startsWith("/experiments");

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
            <small>研究与证据</small>
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
            <span>因子研究工作台</span>
            <span className="readonly-pill">READ ONLY</span>
          </div>
          <div className="asof-control">
            <label htmlFor="as-of-date">{researchContext ? "查询截止" : "证据日期"}</label>
            <input
              id="as-of-date"
              type="date"
              value={asOf}
              aria-label={researchContext ? "研究查询截止日期，留空表示最新" : "证据日期，留空表示最新"}
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
              className={pathIsActive(location.pathname, item.path) ? "active" : ""}
              aria-current={pathIsActive(location.pathname, item.path) ? "page" : undefined}
            >
              {item.icon}
              <span>{item.short}</span>
            </RouterLink>
          ))}
          <button
            type="button"
            className={mobile.some((item) => pathIsActive(location.pathname, item.path)) ? "" : "active"}
            aria-label="打开更多页面"
            aria-current={mobile.some((item) => pathIsActive(location.pathname, item.path)) ? undefined : "page"}
            onClick={() => setMobileMenu(true)}
          >
            <MenuOutlined />
            <span>更多</span>
          </button>
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
