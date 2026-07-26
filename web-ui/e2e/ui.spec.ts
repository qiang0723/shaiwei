import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import {
  dataQuality,
  experimentCatalog,
  experimentCorrection,
  experimentG1,
  experimentOriginal,
  EXPERIMENT_CORRECTION_ID,
  EXPERIMENT_G1_ID,
  EXPERIMENT_ORIGINAL_ID,
  factorCatalog,
  factorCompare,
  factorDetail,
  factorHistory,
  FACTOR_A,
  FACTOR_B,
  forward,
  nav,
  notification,
  overview,
  portfolio,
  replay,
  response,
  signal,
  systemRuns,
  VERSION_A,
  VERSION_B
} from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
});

function experimentCatalogFor(url: URL) {
  const filterKeys = [
    "experiment_kind",
    "research_family",
    "evidence_tier",
    "authority_status",
    "lifecycle_status",
    "outcome_status",
    "evidence_status"
  ] as const;
  const asOf = url.searchParams.get("as_of");
  const asOfItems = experimentCatalog.items.filter(
    (item) => !asOf || item.recorded_at.slice(0, 10) <= asOf
  );
  const filtered = asOfItems.filter((item) => filterKeys.every((key) => {
    const requested = url.searchParams.get(key);
    return !requested || item[key] === requested;
  }));
  const offset = Number(url.searchParams.get("offset") ?? "0");
  const limit = Number(url.searchParams.get("limit") ?? "25");
  const items = filtered.slice(offset, offset + limit);
  return {
    ...experimentCatalog,
    items,
    counters: {
      projected_total_count: experimentCatalog.items.length,
      as_of_count: asOfItems.length,
      filtered_count: filtered.length,
      returned_count: items.length,
      kind_counts: {
        p2_effect_correction: asOfItems.filter((item) => item.experiment_kind === "p2_effect_correction").length,
        p2_effect_original: asOfItems.filter((item) => item.experiment_kind === "p2_effect_original").length,
        p2_engineering_run: asOfItems.filter((item) => item.experiment_kind === "p2_engineering_run").length,
        research_experiment: asOfItems.filter((item) => item.experiment_kind === "research_experiment").length
      }
    },
    filters: Object.fromEntries([
      ...filterKeys.map((key) => [key, url.searchParams.get(key)]),
      ["as_of", asOf]
    ]),
    page: {
      offset,
      limit,
      has_previous: offset > 0,
      has_more: offset + items.length < filtered.length,
      previous_offset: offset > 0 ? Math.max(0, offset - limit) : null,
      next_offset: offset + items.length < filtered.length ? offset + items.length : null
    },
    historical_response_banner: asOf ? "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" : null
  };
}

function experimentDetailFor(url: URL) {
  const original = url.pathname.endsWith(`/${EXPERIMENT_ORIGINAL_ID}`);
  const correction = url.pathname.endsWith(`/${EXPERIMENT_CORRECTION_ID}`);
  const detail = original ? experimentOriginal : correction ? experimentCorrection : experimentG1;
  return {
    ...detail,
    historical_response_banner: url.searchParams.has("as_of")
      ? "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS"
      : null
  };
}

async function mockApi(
  page: Page,
  requests: string[] = [],
  options: { delayFilteredExperimentCatalog?: boolean } = {}
) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url.pathname);
    if (
      options.delayFilteredExperimentCatalog &&
      url.pathname === "/api/v1/experiments" &&
      url.searchParams.has("outcome_status")
    ) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    const requestedVersion = url.searchParams.get("version");
    const historicalBanner = url.searchParams.has("as_of")
      ? "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS"
      : null;
    const data = url.pathname === "/api/v1/experiments"
      ? experimentCatalogFor(url)
      : /^\/api\/v1\/experiments\/(research_experiment|p2_effect_original|p2_effect_correction)\//.test(url.pathname)
        ? experimentDetailFor(url)
        : url.pathname === "/api/v1/factors/compare"
      ? factorCompare
      : url.pathname.endsWith("/admissions")
        ? { ...factorHistory, historical_response_banner: historicalBanner }
        : /^\/api\/v1\/factors\/[0-9a-f]{64}$/.test(url.pathname)
          ? {
              ...factorDetail,
              factor_id: url.pathname.split("/").at(-1),
              factor_version: requestedVersion ?? factorDetail.factor_version,
              sections: {
                ...factorDetail.sections,
                identity: {
                  ...factorDetail.sections.identity,
                  candidate_experiment_id: requestedVersion ?? factorDetail.factor_version
                }
              },
              historical_response_banner: historicalBanner
            }
          : url.pathname === "/api/v1/factors"
            ? { ...factorCatalog, historical_response_banner: historicalBanner }
            : url.pathname.endsWith("/data-quality")
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
      body: JSON.stringify(response(data, url.searchParams.get("as_of")))
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
  const result = await page.evaluate(() => {
    const clientWidth = document.documentElement.clientWidth;
    const overflow = document.documentElement.scrollWidth > clientWidth + 1;
    const offenders = overflow
      ? [...document.querySelectorAll("body *")]
          .filter((element) => element.getBoundingClientRect().right > clientWidth + 1)
          .slice(0, 10)
          .map((element) => ({
            className: element.className?.toString().slice(0, 120) ?? "",
            right: Math.round(element.getBoundingClientRect().right),
            tag: element.tagName,
            text: element.textContent?.trim().slice(0, 80) ?? ""
          }))
      : [];
    return { overflow, offenders };
  });
  expect(result).toEqual({ overflow: false, offenders: [] });
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

test("factor catalog tells the zero-library truth and launches a strict comparison", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto("/factors");
  await expect(page.getByRole("heading", { name: "当前有什么可用因子，为什么还没有入库" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /正式因子库 0/ })).toBeVisible();
  await expect(page.getByText("10", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("8", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("2", { exact: true }).first()).toBeVisible();
  expect(requests).toEqual(["/api/v1/factors"]);

  await page.getByLabel("生命周期筛选").click();
  await page.getByLabel("生命周期筛选").press("ArrowDown");
  await page.getByLabel("生命周期筛选").press("Enter");
  await expect(page.locator("strong:visible", { hasText: "正式因子库仍为 0" })).toBeVisible();
  await page.locator("button:visible", { hasText: "查看全部研究证据" }).click();

  await page.getByRole("checkbox", { name: /111111111111/ }).check();
  await page.getByRole("checkbox", { name: /222222222222/ }).check();
  await page.getByRole("button", { name: "严格比较所选因子" }).click();
  await expect(page).toHaveURL(comparePathForTest([VERSION_A, VERSION_B]));
  await expect(page.getByRole("heading", { name: "只比较同口径的当前权威版本" })).toBeVisible();
  expect(requests).toEqual(["/api/v1/factors", "/api/v1/factors/compare"]);
  await captureVisual(page, testInfo, "factor-compare");
  await expectNoPageOverflow(page);
});

test("factor tear sheet keeps fifteen gates, unavailable evidence and append-only history", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto(`/factors/${FACTOR_A}?version=${VERSION_A}`);
  await expect(page.getByRole("heading", { name: "单因子研究证据" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "全部准入门" })).toBeVisible();
  await expect(page.getByText(/未通过：/)).toContainText("Newey-West(10) t");
  await expect(page.getByText("NOT_EVALUATED · recomputed=false")).toHaveCount(4);
  expect(requests).toEqual([`/api/v1/factors/${FACTOR_A}`]);
  await captureVisual(page, testInfo, "factor-detail");

  await page.getByRole("link", { name: /准入历史/ }).click();
  await expect(page).toHaveURL(`/factors/${FACTOR_A}/admissions`);
  await expect(page.getByRole("heading", { name: "旧判决保留，当前权威另列" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /2 条准入判决/ })).toBeVisible();
  expect(requests).toEqual([
    `/api/v1/factors/${FACTOR_A}`,
    `/api/v1/factors/${FACTOR_A}/admissions`
  ]);
  await expectNoPageOverflow(page);
});

test("experiment catalog separates records from valid models and preserves exact filters", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests, { delayFilteredExperimentCatalog: true });
  await page.goto("/experiments");
  await expect(page.getByRole("heading", { name: "这些实验是什么，哪些结论当前有效" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "4 条实验记录，不是 4 个有效模型" })).toBeVisible();
  await expect(page.getByText("READ ONLY · NO RANKING")).toBeVisible();
  expect(requests).toEqual(["/api/v1/experiments"]);

  await page.getByLabel("结论语义筛选").click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option")
    .filter({ hasText: "方法已失效 · INVALIDATED_METHOD" })
    .click();
  await expect(page).toHaveURL(/outcome_status=INVALIDATED_METHOD/);
  await expect(page.getByText("正在核对实验目录、权威覆盖与分页身份…")).toBeVisible();
  await expect(page.locator(`[title="${EXPERIMENT_CORRECTION_ID}"]`)).toHaveCount(0);
  await expect(page.locator(`[title="${EXPERIMENT_ORIGINAL_ID}"]:visible`).first()).toBeVisible();
  await expect(page.getByText(EXPERIMENT_CORRECTION_ID, { exact: true })).toHaveCount(0);
  await captureVisual(page, testInfo, "experiment-catalog");
  await expectNoPageOverflow(page);
});

test("invalidated P2 evidence links to the authoritative correction without inventing NAV", async ({ page }, testInfo) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto(`/experiments/p2_effect_original/${EXPERIMENT_ORIGINAL_ID}?as_of=2026-07-24`);
  await expect(page.getByRole("heading", { name: "实验结论与证据" })).toBeVisible();
  await expect(page.getByText("历史记录已应用当前权威覆盖")).toBeVisible();
  await expect(page.getByText(/方法已失效：以下旧数值可复算/)).toBeVisible();
  await expect(page.getByText("可复算 · 非权威")).toBeVisible();
  await expect(page.getByRole("region", { name: "P2 窗口与成本精确数据" }).getByRole("row")).toHaveCount(4);
  await expect(page.getByText("没有逐日 NAV，页面不绘制净值、日回撤或交易时序")).toBeVisible();
  await captureVisual(page, testInfo, "experiment-invalidated-detail");

  await page.getByRole("link", { name: "查看权威纠错实验" }).click();
  await expect(page).toHaveURL(new RegExp(`/p2_effect_correction/${EXPERIMENT_CORRECTION_ID}\\?as_of=2026-07-24`));
  await expect(page.getByText("权威历史 REJECT")).toBeVisible();
  await expect(page.getByText(/当前权威历史效果结论为 REJECT/)).toBeVisible();
  expect(requests).toEqual([
    `/api/v1/experiments/p2_effect_original/${EXPERIMENT_ORIGINAL_ID}`,
    `/api/v1/experiments/p2_effect_correction/${EXPERIMENT_CORRECTION_ID}`
  ]);
  await expectNoPageOverflow(page);
});

test("G1 experiment detail renders all fifteen gates from one typed response", async ({ page }) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto(`/experiments/research_experiment/${EXPERIMENT_G1_ID}`);
  await expect(page.getByRole("heading", { name: "全部 G1 门" })).toBeVisible();
  await expect(page.getByRole("region", { name: "实验 G1 十五门" }).getByRole("row")).toHaveCount(16);
  await expect(page.getByText("G1 未准入 · G1_REJECTED")).toBeVisible();
  expect(requests).toEqual([`/api/v1/experiments/research_experiment/${EXPERIMENT_G1_ID}`]);
  await expectNoPageOverflow(page);
});

test("historical factor view applies the authority banner and sends no compare request", async ({ page }) => {
  const requests: string[] = [];
  await mockApi(page, requests);
  await page.goto("/factors?as_of=2026-07-23");
  await expect(page.getByText("历史记录已应用当前权威覆盖")).toBeVisible();
  await expect(page.getByText("历史查询不允许因子比较")).toBeVisible();
  await expect(page.getByLabel("研究查询截止日期，留空表示最新")).toHaveValue("2026-07-23");
  await expect(page.getByRole("checkbox", { name: /111111111111/ })).toBeDisabled();
  expect(requests).toEqual(["/api/v1/factors"]);
});

test("factor comparison conflict keeps selections and renders no charts", async ({ page }) => {
  await page.route("**/api/v1/factors/compare**", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        schema_version: "web-v1",
        request_id: "factor-conflict",
        error: { code: "CONFLICT", message: "因子版本不具备严格可比性", retryable: false }
      })
    });
  });
  await page.goto(comparePathForTest([VERSION_A, VERSION_B]));
  await expect(page.getByRole("heading", { name: "所选因子不具备严格可比性" })).toBeVisible();
  await expect(page.getByText(VERSION_A)).toBeVisible();
  await expect(page.getByText(VERSION_B)).toBeVisible();
  await expect(page.getByRole("heading", { name: "六窗口 RankIC 稳定性" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "压力期最大回撤" })).toHaveCount(0);
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
  for (const route of [
    "/overview",
    "/factors",
    "/experiments",
    `/experiments/p2_effect_correction/${EXPERIMENT_CORRECTION_ID}`,
    "/paper",
    "/signals",
    "/data-quality",
    "/system-runs"
  ]) {
    await page.goto(route);
    await page.locator("h1").waitFor();
    await expectNoCriticalAccessibilityViolations(page);
  }
});

function comparePathForTest(versions: string[]) {
  const search = new URLSearchParams();
  versions.forEach((version) => search.append("version", version));
  return `/factors/compare?${search.toString()}`;
}
