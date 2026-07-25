import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  { route: "/overview", heading: "今天可信、有效、要行动吗" },
  { route: "/paper", heading: "实际成交后，账户发生了什么" },
  { route: "/signals", heading: "为什么入选，今天是否需要调仓" }
];

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

test("overview first contentful paint stays within the local budget", async ({ page }) => {
  await page.goto("/overview", { waitUntil: "networkidle" });
  const firstContentfulPaint = await page.evaluate(() => {
    const entry = performance.getEntriesByName("first-contentful-paint")[0];
    return entry?.startTime ?? null;
  });
  expect(firstContentfulPaint).not.toBeNull();
  expect(firstContentfulPaint as number).toBeLessThanOrEqual(2_000);
});
