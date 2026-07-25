import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import {
  dataQuality,
  forward,
  nav,
  notification,
  overview,
  portfolio,
  replay,
  response,
  signal,
  systemRuns
} from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
});

async function mockApi(page: Page, requests: string[] = []) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url.pathname);
    const data = url.pathname.endsWith("/data-quality")
      ? dataQuality
      : url.pathname.endsWith("/system/runs")
        ? systemRuns
        : url.pathname.includes("/notifications/")
          ? notification
          : url.pathname.endsWith("/overview")
      ? overview
      : url.pathname.endsWith("/portfolio")
        ? portfolio
        : url.pathname.endsWith("/nav")
          ? nav
          : url.pathname.endsWith("/forward")
            ? forward
            : url.pathname.endsWith("/replay")
              ? replay
              : signal;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response(data))
    });
  });
}

async function expectNoCriticalAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter(
    (violation) => violation.impact === "critical" || violation.impact === "serious"
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

async function expectNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  );
  expect(overflow).toBe(false);
}

async function captureVisual(page: Page, testInfo: TestInfo, name: string) {
  if (process.env.P3_CAPTURE !== "1") return;
  await page.screenshot({
    path: testInfo.outputPath("visual", `${name}-${testInfo.project.name}.png`),
    fullPage: true
  });
}

test("overview uses one atomic response and preserves as_of during drilldown", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto("/overview?as_of=2026-07-24");
  await expect(page.getByRole("heading", { name: "今天可信、有效、要行动吗" })).toBeVisible();
  await expect(page.getByText("-0.55 个百分点")).toBeVisible();
  await expect(page.getByText("核心任务", { exact: true })).toBeVisible();
  await captureVisual(page, testInfo, "overview");
  expect(requests).toEqual(["/api/v1/overview"]);
  await page.getByRole("link", { name: /查看完整组合证据/ }).click();
  await expect(page).toHaveURL(/\/paper\?as_of=2026-07-24/);
  await expect(page.getByRole("heading", { name: "实际成交后，账户发生了什么" })).toBeVisible();
  await expectNoPageOverflow(page);
});

test("paper separates forward performance from full-account audit and exposes day evidence", async ({ page }, testInfo) => {
  await mockApi(page);
  await page.goto("/paper");
  await expect(page.getByRole("heading", { name: "实际成交后，账户发生了什么" })).toBeVisible();
  await expect(page.getByText("FORWARD", { exact: true }).first()).toBeVisible();
  await captureVisual(page, testInfo, "paper");
  await expect(page.getByText(/BACKFILL 仅作工程与账务审计/)).toBeHidden();
  await page.getByText("全账户", { exact: true }).click();
  await expect(page.getByText(/BACKFILL 仅作工程与账务审计/)).toBeVisible();
  await page.getByRole("button", { name: "2026-07-24" }).click();
  await expect(page.getByText("产物哈希")).toBeVisible();
  await page.keyboard.press("Escape");
  await expectNoPageOverflow(page);
});

test("signals keep planned deltas separate from execution facts", async ({ page }, testInfo) => {
  await mockApi(page);
  await page.goto("/signals");
  await expect(page.getByRole("heading", { name: "为什么入选，今天是否需要调仓" })).toBeVisible();
  await expect(page.getByText("执行日证据尚未到期")).toBeVisible();
  await expect(page.getByText("实际交易腿")).toBeVisible();
  await captureVisual(page, testInfo, "signals");
  await page.getByRole("button", { name: "688008.SH" }).click();
  await expect(page.getByText("暂无可审计的因子贡献分解")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel("搜索证券代码").fill("999999");
  await expect(page.getByText("当前筛选没有目标")).toBeVisible();
  await expectNoPageOverflow(page);
});

test("data quality keeps PASS separate from evidence WARN and does not invent a trend", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto("/data-quality?as_of=2026-07-24");
  await expect(page.getByRole("heading", { name: "这批数据，足以支持今天的信号吗" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据门通过，可进入已冻结的信号流程" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据仍有明确缺口，不能宣称全量重验" })).toBeVisible();
  await expect(page.getByText("IDENTITY_MATCH_UNHASHED")).toBeVisible();
  await expect(page.getByText("NOT_APPLICABLE", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据哨兵矩阵" })).toBeVisible();
  await captureVisual(page, testInfo, "data-quality");
  expect(requests).toEqual(["/api/v1/data-quality"]);
  await expectNoPageOverflow(page);
});

test("system runs preserves recovery and opens notification as a separate snapshot", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto("/system-runs");
  await expect(page.getByRole("heading", { name: "今天的运行闭环，在哪里失败过、是否恢复" })).toBeVisible();
  await expect(page.getByText("ForwardQlibError", { exact: true })).toBeVisible();
  await expect(page.getByText("Legacy 不可寻址")).toBeVisible();
  await captureVisual(page, testInfo, "system-runs");
  await page.getByRole("button", { name: /ce3bfbf96e9ec474/ }).click();
  await expect(page.getByText("这是独立证据切片")).toBeVisible();
  await expect(page.getByText("NetworkError")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /ce3bfbf96e9ec474/ })).toBeFocused();
  expect(requests).toEqual([
    "/api/v1/system/runs",
    "/api/v1/notifications/ce3bfbf96e9ec474"
  ]);
  await expectNoPageOverflow(page);
});

test("refresh keeps old evidence visible and an error blocks stale numbers before retry", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-1440");
  let attempt = 0;
  await page.route("**/api/v1/overview**", async (route) => {
    attempt += 1;
    if (attempt === 2) await new Promise((resolve) => setTimeout(resolve, 500));
    if (attempt === 3) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: "web-v1",
          request_id: "e2e-error",
          error: { code: "UPSTREAM_UNAVAILABLE", message: "只读查询服务不可用", retryable: true }
        })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response(overview))
    });
  });

  await page.goto("/overview");
  await expect(page.getByText("-0.55 个百分点")).toBeVisible();
  await page.getByLabel("证据日期，留空表示最新").fill("2026-07-23");
  await expect(page.getByRole("status").filter({ hasText: "刷新中" })).toBeVisible();
  await expect(page.getByText("-0.55 个百分点")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "刷新中" })).toBeHidden();

  await page.getByLabel("证据日期，留空表示最新").fill("2026-07-22");
  await expect(page.getByRole("heading", { name: "只读查询服务不可用" })).toBeVisible();
  await expect(page.getByText("-0.55 个百分点")).toBeHidden();
  await page.getByRole("button", { name: "重新读取" }).click();
  await expect(page.getByRole("heading", { name: "今天可信、有效、要行动吗" })).toBeVisible();
});

test("primary routes have no serious or critical axe violations", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-1440" && testInfo.project.name !== "mobile-390");
  await mockApi(page);
  for (const route of ["/overview", "/paper", "/signals", "/data-quality", "/system-runs"]) {
    await page.goto(route);
    await page.locator("h1").waitFor();
    await expectNoCriticalAccessibilityViolations(page);
  }
});
