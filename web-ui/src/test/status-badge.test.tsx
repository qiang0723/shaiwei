import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("uses readable text in addition to color", () => {
    render(<StatusBadge status="WARN" />);
    const badge = screen.getByText("需关注");
    expect(badge).toBeVisible();
    expect(badge.closest(".ant-tag")).toHaveAttribute("title", "需关注 · WARN");
    expect(screen.queryByText("WARN", { exact: true })).not.toBeInTheDocument();
  });
});
