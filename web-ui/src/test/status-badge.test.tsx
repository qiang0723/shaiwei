import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("uses readable text in addition to color", () => {
    render(<StatusBadge status="WARN" />);
    expect(screen.getByText("需关注 · WARN")).toBeVisible();
  });
});
