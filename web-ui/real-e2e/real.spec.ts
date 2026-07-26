import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  { route: "/overview", heading: "今天可信、有效、要行动吗" },
  { route: "/paper", heading: "实际成交后，账户发生了什么" },
  { route: "/signals", heading: "为什么入选，今天是否需要调仓" },
  { route: "/data-quality", heading: "这批数据，足以支持今天的信号吗" },
  { route: "/system-runs", heading: "今天的运行闭环，在哪里失败过、是否恢复" },
  { route: "/factors", heading: "当前有什么可用因子，为什么还没有入库" },
  { route: "/experiments", heading: "这些实验是什么，哪些结论当前有效" }
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
    }>;
    sorted_by_performance: false;
  };
  meta: { as_of: string };
}

test("deployed read-only UI serves real evidence under strict CSP", async ({ page, baseURL }) => {
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
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
    expect(cspViolations).toEqual([]);
  }

  expect(errors).toEqual([]);
  expect([...foreignOrigins]).toEqual([]);
});

test("root route enters overview without changing evidence date semantics", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { name: "今天可信、有效、要行动吗" })).toBeVisible();
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
  await expect(page.getByText("NOT_EVALUATED · recomputed=false", { exact: true })).toHaveCount(4);

  await page.goto(`/factors/${first!.factor_id}/admissions`);
  await expect(page.getByRole("heading", { name: "旧判决保留，当前权威另列" })).toBeVisible();
  await expect(page.getByRole("region", { name: "因子准入历史" })).toBeVisible();

  const parameters = new URLSearchParams();
  parameters.append("version", first!.current_factor_version);
  parameters.append("version", second!.current_factor_version);
  await page.goto(`/factors/compare?${parameters.toString()}`);
  await expect(page.getByRole("heading", { name: "只比较同口径的当前权威版本" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "六窗口 RankIC 稳定性" })).toBeVisible();
  await expect(page.getByText("后端 fingerprint 是唯一裁判；选择顺序保留，结果不按表现重排。"))
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
  await expect(page.getByText("权威历史 REJECT")).toBeVisible();
  await expect(page.getByText("历史效果拒绝 · HISTORICAL_EFFECT_REJECTED")).toBeVisible();
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
