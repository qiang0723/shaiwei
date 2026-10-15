import { describe, expect, it } from "vitest";
import { CARRIED_NO_SCORE_LABEL, formatSignalScore } from "../pages/SignalsPage";

describe("signal score display (shadow-carry-suspended-v1)", () => {
  it("shows the carried label for a null score instead of zero", () => {
    expect(formatSignalScore(null)).toBe(CARRIED_NO_SCORE_LABEL);
    expect(formatSignalScore(null)).not.toContain("0.000000");
  });

  it("keeps the six-digit format for live scores", () => {
    expect(formatSignalScore(0.1234567)).toBe("0.123457");
    expect(formatSignalScore(0)).toBe("0.000000");
  });
});
