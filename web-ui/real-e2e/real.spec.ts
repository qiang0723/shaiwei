import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  { route: "/overview", heading: "今天可信、有效、要行动吗" },
  { route: "/paper", heading: "实际成交后，账户发生了什么" },
  { route: "/signals", heading: "为什么入选，今天是否需要调仓" },
  { route: "/data-quality", heading: "这批数据，足以支持今天的信号吗" },
  { route: "/system-runs", heading: "今天的运行闭环，在哪里失败过、是否恢复" },
  { route: "/factors", heading: "当前有什么可用因子，为什么还没有入库" }
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

test("overview first contentful paint stays within the local budget", async ({ page }) => {
  await page.goto("/overview", { waitUntil: "networkidle" });
  const firstContentfulPaint = await page.evaluate(() => {
    const entry = performance.getEntriesByName("first-contentful-paint")[0];
    return entry?.startTime ?? null;
  });
  expect(firstContentfulPaint).not.toBeNull();
  expect(firstContentfulPaint as number).toBeLessThanOrEqual(2_000);
});
