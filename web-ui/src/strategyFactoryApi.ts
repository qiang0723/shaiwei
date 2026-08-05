import { UiQueryError } from "./api";
import type { StrategyFactoryData } from "./strategyFactoryTypes";
import type { ApiEnvelope, ApiErrorEnvelope } from "./types";
import { assertEnvelope } from "./validation";
import { assertStrategyFactory } from "./validation/strategyFactory";

export async function fetchStrategyFactory(
  signal: AbortSignal
): Promise<ApiEnvelope<StrategyFactoryData>> {
  let response: Response;
  try {
    response = await fetch("/api/v1/strategy-factory", {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new UiQueryError("UPSTREAM_UNAVAILABLE", "策略工厂只读查询当前不可用", {
      retryable: true
    });
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new UiQueryError("INVALID_RESPONSE", "策略工厂返回了无效响应");
  }
  if (!response.ok) {
    const failure = body as ApiErrorEnvelope;
    throw new UiQueryError(
      failure.error?.code ?? "QUERY_FAILED",
      failure.error?.message ?? "策略工厂只读查询失败",
      {
        requestId: failure.request_id,
        retryable: failure.error?.retryable
      }
    );
  }
  try {
    assertEnvelope(body);
    assertStrategyFactory(body.data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "策略工厂证据校验失败";
    throw new UiQueryError("EVIDENCE_MISMATCH", message, {
      requestId: (body as Partial<ApiEnvelope<StrategyFactoryData>>).request_id
    });
  }
  return body as ApiEnvelope<StrategyFactoryData>;
}
