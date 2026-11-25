import { expect, test, type Page } from "@playwright/test";
test("newly signed-in roles can immediately load every protected dashboard request", async ({page}) => {
  await page.goto("/");
  for (const [role, heading] of [
    ["Faculty", "My Teaching Workspace"], ["Admin", "Institutional Command Center"],
    ["Student", "My Academic Workspace"], ["HOD", "Department Command Center"],
    ["Operator", "Campus Operations Center"], ["Admin", "Institutional Command Center"]
  ]) {
    await page.getByRole("button", { name: role, exact: true }).click();
    await expect(page.getByRole("heading", {name:heading})).toBeVisible();
    await logout(page);
  }
});
async function logout(page: Page) {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
}
test("faculty report → administrator approval → student notification", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await page.screenshot({ path: info.outputPath("login.png") });
  await page.getByRole("button", { name: "Faculty", exact: true }).click();
  await page
    .getByRole("button", { name: "Report absence", exact: true })
    .click();
  await page
    .getByLabel("Private reason (optional)")
    .fill("Confidential appointment");
  await page.getByRole("button", { name: "Submit absence" }).click();
  await expect(page.getByRole("dialog")).toContainText("2 affected sessions");
  await page.getByRole("button", { name: "View my reports" }).click();
  await logout(page);
  await page.getByRole("button", { name: "Admin", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Institutional Command Center" }),
  ).toBeVisible();
  await page.screenshot({ path: info.outputPath("dashboard.png") });
  await page.getByRole("button", { name: "View recovery plans" }).click();
  await page.getByRole("button", { name: "Approve plan" }).first().click();
  await page.getByRole("button", { name: "Confirm and publish" }).click();
  await expect(page.getByText("Timetable v2 published")).toBeVisible();
  await logout(page);
  await page.getByRole("button", { name: "Student", exact: true }).click();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(page.getByText("Published v2")).toBeVisible();
  await expect(page.getByText("Recovered", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: /Notifications/ }).click();
  await expect(
    page.getByText("Algorithms timetable update", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Confidential appointment")).toHaveCount(0);
});
test("mobile operator simulates a power cascade without publication", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Operator", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Campus Operations Center" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Scenario lab" }).click();
  await page
    .getByRole("button", { name: "Building power failure", exact: true })
    .click();
  await page.getByRole("button", { name: "Run impact analysis" }).click();
  await expect(
    page.getByRole("heading", { name: "Simulated impact" }),
  ).toBeVisible();
  await expect(
    page.getByText("Impact 2 · Systems Lab A", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve plan" })).toHaveCount(
    0,
  );
});
test("administrator edits a capacity, inspects audit and switches calendar views", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Admin", exact: true }).click();
  await page.getByRole("link", { name: "Resources", exact: true }).click();
  await page.getByRole("button", { name: "Room 101", exact: true }).click();
  await page.getByRole("button", { name: "Edit resource" }).click();
  await page.getByLabel("Seat capacity").fill("45");
  await page.getByRole("button", { name: "Save resource" }).click();
  await expect(page.getByText("Directory updated")).toBeVisible();
  await page.getByRole("link", { name: "Audit history" }).click();
  await expect(page.getByText("Updated classroom · Room 101")).toBeVisible();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await expect(page.locator(".weekgrid>div")).toHaveCount(7);
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("button", { name: "Add account" })).toBeVisible();
});
