import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  { route: "/overview", heading: "今日概览" },
  { route: "/strategy-factory", heading: "策略工厂" },
  { route: "/paper", heading: "模拟组合" },
  { route: "/signals", heading: "股票池与信号" },
  { route: "/data-quality", heading: "数据质量" },
  { route: "/system-runs", heading: "系统运行" },
  { route: "/factors", heading: "因子工厂" },
  { route: "/experiments", heading: "研究证据" }
];

interface RealFactorCatalog {
  data: {
    counters: {
      formal_library_count: number;
      researched_factor_count: number;
      authoritative_rejected_count: number;
      historical_only_count: number;
    };
    items: Array<{
      factor_id: string;
      current_factor_version: string | null;
      research_family: string;
    }>;
  };
  meta: { as_of: string };
}

interface RealExperimentCatalog {
  data: {
    counters: {
      projected_total_count: number;
      kind_counts: Record<string, number>;
    };
    items: Array<{
      experiment_kind: string;
      experiment_id: string;
      outcome_status: string;
      authority_status: string;
    }>;
    sorted_by_performance: false;
  };
  meta: { as_of: string };
}

interface RealStrategyFactory {
  data: {
    summary: {
      registered_universe_count: number;
      research_eligible_universe_count: number;
      blocked_universe_count: number;
      admitted_factor_count: number;
      active_authorized_task_count: number;
    };
    authority_projection_version: string;
    route_decision: {
      status: string;
      primary_goal: { live_dual_days_at_freeze: number; minimum_live_dual_days: number };
      m7: { candidate_count: number; effect_read_count: number; strategy_effective: string };
    };
    recent_gate_decisions: Array<{
      terminal_state: string;
      evidence_tier: string;
      strategy_effective: string;
      effect_read: boolean;
      conflict_group_count: number;
      forward_only_group_count: number;
      pit_resolved_group_count: number;
      route_status: string;
      production_authorization: string;
      release_scope_sha256: string;
    }>;
    active_tasks: unknown[];
    invariants: {
      web_read_only: boolean;
      external_calls_made: number;
      real_research_runs: number;
      bse_count: number;
    };
  };
}

test("deployed read-only UI serves real evidence under strict CSP", async ({ page, baseURL }, testInfo) => {
  const errors: string[] = [];
  const foreignOrigins = new Set<string>();
  page.on("pageerror", (error) => errors.push(`pageerror:${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console:${message.text()}`);
  });
  page.on("request", (request) => {
    const origin = new URL(request.url()).origin;
    if (baseURL && origin !== new URL(baseURL).origin) foreignOrigins.add(origin);
  });
  await page.addInitScript(() => {
    const violations: Array<Record<string, string | number>> = [];
    Object.defineProperty(window, "__p3CspViolations", { value: violations, writable: false });
    document.addEventListener("securitypolicyviolation", (event) => {
      violations.push({
        blockedURI: event.blockedURI,
        directive: event.violatedDirective,
        sample: event.sample,
        sourceFile: event.sourceFile,
        lineNumber: event.lineNumber,
        columnNumber: event.columnNumber
      });
    });
  });

  for (const item of pages) {
    const response = await page.goto(item.route);
    expect(response?.status()).toBe(200);
    const csp = response?.headers()["content-security-policy"] ?? "";
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).not.toContain("'unsafe-inline'");
    expect(csp).not.toContain("'unsafe-eval'");
    await expect(page.getByRole("heading", { name: item.heading })).toBeVisible();
    const cspViolations = await page.evaluate(
      () => (window as Window & { __p3CspViolations?: Array<Record<string, string | number>> }).__p3CspViolations ?? []
    );
    const results = await new AxeBuilder({ page }).analyze();
    const blocking = results.violations.filter(
      (violation) => violation.impact === "critical" || violation.impact === "serious"
    );
    const pageWidth = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth
    }));
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
    expect(pageWidth.scrollWidth).toBeLessThanOrEqual(pageWidth.clientWidth + 1);
    expect(cspViolations).toEqual([]);
    if (item.route === "/experiments") {
      const catalogResponse = await page.request.get("/api/v1/experiments?limit=25&offset=0");
      expect(catalogResponse.status()).toBe(200);
      const catalog = await catalogResponse.json() as RealExperimentCatalog;
      const primaryCatalog = testInfo.project.name === "real-mobile"
        ? page.getByRole("table", { name: "移动端实验目录" })
        : page.locator(".experiment-desktop-catalog");
      const primaryCatalogText = await primaryCatalog.innerText();
      for (const experiment of catalog.data.items) {
        expect(primaryCatalogText).not.toContain(experiment.experiment_id);
      }
      await expect(primaryCatalog.getByText("实验 1", { exact: true })).toBeVisible();
    }
    if (item.route === "/experiments" && testInfo.project.name === "real-mobile") {
      const mobileCatalog = page.getByRole("table", { name: "移动端实验目录" });
      await expect(mobileCatalog).toBeVisible();
      await expect(page.locator(".experiment-desktop-catalog")).toBeHidden();
      const visibleStatuses = await mobileCatalog.locator(".experiment-mobile-status").allInnerTexts();
      expect(visibleStatuses.length).toBeGreaterThan(0);
      expect(visibleStatuses.every((status) => !/[A-Z]{3,}(?:_[A-Z]+)+/.test(status))).toBe(true);
      const rowHeights = await mobileCatalog.locator(".experiment-catalog-card").evaluateAll(
        (rows) => rows.map((row) => row.getBoundingClientRect().height)
      );
      expect(Math.max(...rowHeights)).toBeLessThanOrEqual(72);
    }
    if (item.route === "/strategy-factory") {
      const response = await page.request.get("/api/v1/strategy-factory");
      expect(response.status()).toBe(200);
      const factory = await response.json() as RealStrategyFactory;
      expect(factory.data.summary).toMatchObject({
        registered_universe_count: 8,
        research_eligible_universe_count: 5,
        blocked_universe_count: 3,
        admitted_factor_count: 0,
        active_authorized_task_count: 0
      });
      expect(factory.data.active_tasks).toEqual([]);
      expect(factory.data.route_decision).toMatchObject({
        status: "COURSE_CORRECTION_AND_OBSERVE",
        primary_goal: { live_dual_days_at_freeze: 5, minimum_live_dual_days: 20 },
        m7: { candidate_count: 0, effect_read_count: 0, strategy_effective: "NOT_EVALUATED" }
      });
      expect(factory.data.authority_projection_version).toBe(
        "m5-strategy-factory-authority-projection-v1"
      );
      expect(factory.data.recent_gate_decisions).toHaveLength(1);
      const gate = factory.data.recent_gate_decisions[0]!;
      expect(gate).toMatchObject({
        terminal_state: "BLOCKED_DATA",
        evidence_tier: "LINEAGE_NO_GO_ONLY",
        strategy_effective: "NOT_EVALUATED",
        effect_read: false,
        conflict_group_count: 23,
        forward_only_group_count: 23,
        pit_resolved_group_count: 0,
        route_status: "PAUSE",
        production_authorization: "none"
      });
      expect(factory.data.invariants).toMatchObject({
        web_read_only: true,
        external_calls_made: 0,
        real_research_runs: 0,
        bse_count: 0
      });
      await expect(page.getByRole("heading", {
        name: "动态基本面跨池研究：数据证据阻断，未评价策略效果"
      })).toBeVisible();
      await expect(page.getByText(gate.release_scope_sha256, { exact: true })).toBeHidden();
      await page.locator(".factory-gate-evidence summary").click();
      await expect(page.getByText(gate.release_scope_sha256, { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "提交执行" })).toHaveCount(0);
    }
    const captureDir = process.env.P3_CAPTURE_REAL_DIR;
    const captureRoute = process.env.P3_CAPTURE_REAL_ROUTE;
    if (captureDir && (!captureRoute || captureRoute === item.route)) {
      const name = item.route.slice(1).replaceAll("/", "-") || "root";
      await page.screenshot({
        path: `${captureDir}/${name}-${testInfo.project.name}.png`,
        fullPage: true
      });
    }
  }

  expect(errors).toEqual([]);
  expect([...foreignOrigins]).toEqual([]);
});

test("root route enters overview without changing evidence date semantics", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { name: "今日概览" })).toBeVisible();
});

test("real paper page follows the isolated Top20 evidence state without overclaiming", async ({ page }) => {
  const portfolioResponse = await page.request.get(
    "/api/v1/paper/portfolio?account_id=model_top20"
  );
  const forwardResponse = await page.request.get(
    "/api/v1/paper/forward?account_id=model_top20"
  );
  expect(portfolioResponse.status()).toBe(200);
  expect(forwardResponse.status()).toBe(200);
  const portfolioPayload = await portfolioResponse.json() as {
    data: { account_id: string; mode: string };
  };
  const forwardPayload = await forwardResponse.json() as {
    data: {
      status: string;
      forward_observation_count: number;
      series: unknown[];
      paired_checkpoint: { controlled_catchup_count: number; live_dual_count: number };
    };
  };
  expect(portfolioPayload.data.account_id).toBe("model_top20");
  expect(forwardPayload.data.series).toHaveLength(forwardPayload.data.forward_observation_count);
  if (forwardPayload.data.forward_observation_count === 0) {
    expect(portfolioPayload.data.mode).toBe("BACKFILL");
    expect(forwardPayload.data).toMatchObject({ status: "NOT_READY", series: [] });
  } else {
    expect(portfolioPayload.data.mode).toBe("FORWARD");
  }

  await page.goto("/paper");
  await page.locator(".account-selector-surface")
    .getByText("比较账户 · Top20", { exact: true })
    .click();
  const count = forwardPayload.data.forward_observation_count;
  await expect(page.getByText(
    count === 0
      ? "Top20 当前没有协议 FORWARD，不能与 Top30 比较策略优劣"
      : "Top20 的协议 FORWARD 包含受控补跑，不能全部称为自然前瞻"
  )).toBeVisible();
  const checkpoint = forwardPayload.data.paired_checkpoint;
  await expect(page.getByText(new RegExp(
    `协议 FORWARD ${count} 日 · 受控补跑 ${checkpoint.controlled_catchup_count} 日 · 同日自然 ${checkpoint.live_dual_count} 日`
  )).first()).toBeVisible();
  if (count === 0) {
    await expect(page.getByText("尚无协议 FORWARD 账户日", { exact: true })).toBeVisible();
    await expect(page.getByText("前瞻锚点未形成", { exact: true })).toBeVisible();
  }
  await expect(page.getByText("年化收益")).toHaveCount(0);
  await expect(page.getByText("Sharpe")).toHaveCount(0);
  await expect(page.getByText("信息比率")).toHaveCount(0);
});

test("real primary views keep technical identifiers behind explicit evidence interactions", async ({ page }) => {
  const overviewResponse = await page.request.get("/api/v1/overview");
  const overviewPayload = await overviewResponse.json() as {
    data: { evidence: { data_snapshot_sha256: string } };
  };
  const signalResponse = await page.request.get("/api/v1/signals/latest");
  const signalPayload = await signalResponse.json() as { data: { signal_sha256: string } };
  const qualityResponse = await page.request.get("/api/v1/data-quality");
  const qualityPayload = await qualityResponse.json() as {
    data: { batch_chain: { incremental_batches: Array<{ batch_id: string; content_sha256: string }> } };
  };

  await page.goto("/overview");
  const dataHash = overviewPayload.data.evidence.data_snapshot_sha256;
  await expect(page.getByText(dataHash, { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "查看技术证据" }).click();
  await expect(page.getByText(dataHash, { exact: true })).toBeHidden();
  await page.getByText("展开技术标识与来源").click();
  await expect(page.getByText(dataHash, { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.goto("/signals");
  await expect(page.getByText(signalPayload.data.signal_sha256, { exact: true })).toHaveCount(0);
  await expect(page.getByText("模型、研究环境、代码与数据证据")).toBeVisible();

  await page.goto("/data-quality");
  for (const batch of qualityPayload.data.batch_chain.incremental_batches) {
    await expect(page.getByText(batch.batch_id, { exact: true })).toHaveCount(0);
    await expect(page.getByText(batch.content_sha256, { exact: true })).toHaveCount(0);
  }
  await expect(page.getByText("主视图只显示来源、行数与采集时刻")).toBeVisible();
});

test("real factor projection drives catalog, tear sheet, history and strict comparison", async ({ page }) => {
  const response = await page.request.get("/api/v1/factors");
  expect(response.status()).toBe(200);
  const catalog = await response.json() as RealFactorCatalog;
  expect(catalog.meta.as_of).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(catalog.data.counters).toEqual({
    formal_library_count: 0,
    researched_factor_count: 10,
    authoritative_rejected_count: 8,
    historical_only_count: 2
  });

  const current = catalog.data.items.filter(
    (item): item is typeof item & { current_factor_version: string } => item.current_factor_version !== null
  );
  const first = current[0];
  const second = current.find(
    (item) => item.factor_id !== first?.factor_id && item.research_family === first?.research_family
  );
  expect(first).toBeDefined();
  expect(second).toBeDefined();

  await page.goto(`/factors/${first!.factor_id}?version=${first!.current_factor_version}`);
  await expect(page.getByRole("heading", { name: "单因子研究证据" })).toBeVisible();
  await expect(page.getByRole("region", { name: "G1 十五门" }).getByRole("row")).toHaveCount(16);
  await expect(page.getByText("未评估 · 未在前端补算", { exact: true })).toHaveCount(4);

  await page.goto(`/factors/${first!.factor_id}/admissions`);
  await expect(page.getByRole("heading", { name: "旧判决保留，当前权威另列" })).toBeVisible();
  await expect(page.getByRole("region", { name: "因子准入历史" })).toBeVisible();

  const parameters = new URLSearchParams();
  parameters.append("version", first!.current_factor_version);
  parameters.append("version", second!.current_factor_version);
  await page.goto(`/factors/compare?${parameters.toString()}`);
  await expect(page.getByRole("heading", { name: "只比较同口径的当前权威版本" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "六窗口 RankIC 稳定性" })).toBeVisible();
  await expect(page.getByText("后端一致性校验是唯一裁判；选择顺序保留，结果不按表现重排。"))
    .toBeVisible();
});

test("real experiment projection preserves authority, invalidation and typed effect evidence", async ({ page }) => {
  const catalogResponse = await page.request.get("/api/v1/experiments?limit=25&offset=0");
  expect(catalogResponse.status()).toBe(200);
  const catalog = await catalogResponse.json() as RealExperimentCatalog;
  expect(catalog.data.counters.projected_total_count).toBe(783);
  expect(catalog.data.counters.kind_counts).toEqual({
    p2_effect_correction: 1,
    p2_effect_original: 1,
    p2_engineering_run: 3,
    research_experiment: 778
  });
  expect(catalog.data.sorted_by_performance).toBe(false);

  const originalResponse = await page.request.get(
    "/api/v1/experiments?experiment_kind=p2_effect_original&limit=25&offset=0"
  );
  const originalCatalog = await originalResponse.json() as RealExperimentCatalog;
  const original = originalCatalog.data.items[0];
  expect(original?.outcome_status).toBe("INVALIDATED_METHOD");

  await page.goto(`/experiments/${original!.experiment_kind}/${original!.experiment_id}`);
  await expect(page.getByText(/方法已失效：以下旧数值可复算/)).toBeVisible();
  await expect(page.getByRole("region", { name: "P2 窗口与成本精确数据" }).getByRole("row"))
    .toHaveCount(4);
  await expect(page.getByText("没有逐日 NAV，页面不绘制净值、日回撤或交易时序")).toBeVisible();

  await page.getByRole("link", { name: "查看权威纠错实验" }).click();
  await expect(page.getByText("权威历史拒绝")).toBeVisible();
  await expect(page.getByText("历史效果拒绝", { exact: true })).toBeVisible();
});

test("overview first contentful paint stays within the local budget", async ({ page }) => {
  await page.goto("/overview", { waitUntil: "networkidle" });
  const firstContentfulPaint = await page.evaluate(() => {
    const entry = performance.getEntriesByName("first-contentful-paint")[0];
    return entry?.startTime ?? null;
  });
  expect(firstContentfulPaint).not.toBeNull();
  expect(firstContentfulPaint as number).toBeLessThanOrEqual(2_000);
});
