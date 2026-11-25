import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Modal, Pill } from "./ui";
import { fromTime, time } from "./types";
afterEach(cleanup);
describe("workspace controls", () => {
  it("keeps the status readable without color", () => {
    render(<Pill tone="amber">Pending review</Pill>);
    expect(screen.getByText("Pending review")).toBeTruthy();
  });
  it("exposes a named review dialog and close action", () => {
    const close = vi.fn();
    render(
      <Modal title="Review plan" close={close}>
        Two changes
      </Modal>,
    );
    expect(screen.getByRole("dialog", { name: "Review plan" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(close).toHaveBeenCalledOnce();
  });
  it("round-trips partial-day times and midnight", () => {
    for (const t of ["00:00", "08:15", "17:45", "23:59"])
      expect(time(fromTime(t))).toBe(t);
  });
});
