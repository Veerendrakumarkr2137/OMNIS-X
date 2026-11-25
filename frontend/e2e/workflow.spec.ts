import { expect, test, type Page } from "@playwright/test";

test("an unavailable dashboard file reloads once and offers a retry", async ({
  page,
}) => {
  const asset = "**/assets/Dashboard-*.js";
  let failures = 0;
  await page.route(asset, (route) => {
    failures++;
    return route.fulfill({ status: 404 });
  });
  const response = await page.goto("/");
  expect(response?.headers()["cache-control"]).toBe("no-cache");
  await page.getByRole("button", { name: "Student", exact: true }).click();
  const reload = page.getByRole("button", { name: "Reload page" });
  await expect(reload).toBeVisible();
  expect(failures).toBe(2);
  await page.unroute(asset);
  await reload.click();
  await expect(
    page.getByRole("heading", { name: "My Academic Workspace" }),
  ).toBeVisible();
});

test("newly signed-in roles can immediately load every protected dashboard request", async ({
  page,
}) => {
  await page.goto("/");
  for (const [role, heading] of [
    ["Faculty", "My Teaching Workspace"],
    ["Admin", "Institutional Command Center"],
    ["Student", "My Academic Workspace"],
    ["HOD", "Department Command Center"],
    ["Operator", "Campus Operations Center"],
    ["Admin", "Institutional Command Center"],
  ]) {
    await page.getByRole("button", { name: role, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
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
  browser,
}, info) => {
  const adminContext = await browser.newContext();
  const studentContext = await browser.newContext();
  const admin = await adminContext.newPage();
  const student = await studentContext.newPage();
  await Promise.all([admin.goto("/"), student.goto("/")]);
  await Promise.all([
    admin.getByRole("button", { name: "Admin", exact: true }).click(),
    student.getByRole("button", { name: "Student", exact: true }).click(),
  ]);
  const coverage = admin.getByRole("button", {
    name: /5 of 6 sessions covered/,
  });
  await expect(coverage).toBeVisible();
  const day = await admin.getByLabel("Dashboard date").inputValue();
  await admin.getByRole("button", { name: "Next dashboard day" }).click();
  await expect(admin.getByLabel("Dashboard date")).not.toHaveValue(day);
  await admin.getByRole("button", { name: "Today", exact: true }).click();
  await expect(admin.getByLabel("Dashboard date")).toHaveValue(day);
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
  await expect(
    admin.getByRole("button", { name: /3 of 6 sessions covered/ }),
  ).toBeVisible({ timeout: 12000 });
  await expect(admin.getByText("1 ready · 1 need recalculation")).toBeVisible();
  await expect(student.getByText("At risk", { exact: true })).toBeVisible({
    timeout: 12000,
  });
  await admin.screenshot({ path: info.outputPath("dashboard.png") });
  await admin.getByRole("button", { name: "View recovery plans" }).click();
  await admin.getByRole("button", { name: "Approve plan" }).first().click();
  await admin.getByRole("button", { name: "Confirm and publish" }).click();
  await expect(admin.getByText("Timetable v2 published")).toBeVisible();
  await admin.getByRole("link", { name: "Overview" }).click();
  await expect(coverage).toBeVisible();
  await coverage.click();
  await expect(admin.getByLabel("Timetable date")).toHaveValue(day);
  await expect(student.getByText("Recovered", { exact: true })).toBeVisible({
    timeout: 12000,
  });
  await student.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(student.getByText("Published v2")).toBeVisible();
  await expect(student.getByText("Recovered", { exact: true })).toBeVisible();
  await student.getByRole("link", { name: /Notifications/ }).click();
  await expect(
    student.getByText("Algorithms timetable update", { exact: true }),
  ).toBeVisible();
  await expect(student.getByText("Confidential appointment")).toHaveCount(0);
  await adminContext.close();
  await studentContext.close();
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
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
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
