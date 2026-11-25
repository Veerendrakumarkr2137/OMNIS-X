import { expect, test } from "@playwright/test";
import { shiftDay } from "../src/types";

test.skip(
  process.env.OMNIS_BROWSER_DATASET !== "iiet",
  "Requires the IIET demo database",
);

test("the Digital twin lets department heads follow a room's sessions and dependencies", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "HOD", exact: true }).click();
  await page.getByRole("link", { name: "Digital twin", exact: true }).click();
  await page.getByLabel("Campus model date").fill("2026-11-23");
  await page
    .getByRole("combobox", { name: "Resource category" })
    .selectOption("Rooms & labs");
  await page.getByRole("textbox", { name: "Search resources" }).fill("A126");
  const detail = page.getByRole("region", { name: "Resource details" });
  await expect(
    detail.getByRole("heading", { name: "Room A126" }),
  ).toBeVisible();
  await detail.getByRole("button", { name: /Automata Theory/ }).click();
  await expect(
    detail.getByRole("heading", { name: "Depends on" }),
  ).toBeVisible();
  await detail.getByRole("button", { name: /Dr\. Vikram Nair/ }).click();
  await expect(
    detail.getByRole("heading", { name: "Dr. Vikram Nair" }),
  ).toBeVisible();
  await page.getByLabel("Affected only").check();
  await expect(
    page.getByText("No affected resources for this date."),
  ).toBeVisible();
});

test("the Digital twin switches between resources and the dependency graph", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "HOD", exact: true }).click();
  await page.getByRole("link", { name: "Digital twin", exact: true }).click();
  await page.getByLabel("Campus model date").fill("2026-11-23");
  const search = page.getByRole("textbox", { name: "Search resources" });
  await search.fill("A126");
  await page.getByRole("button", { name: "Graph", exact: true }).click();
  const graph = page.getByRole("region", { name: "Resource dependency graph" });
  await expect(graph).toBeVisible();
  await expect(search).toHaveValue("A126");
  await expect(
    graph.getByLabel("Room A126, Classroom, operational", { exact: true }),
  ).toBeVisible();
  await expect(
    graph.locator(".react-flow__node").filter({ hasNotText: "A126" }),
  ).toHaveCount(0);
  await search.clear();
  await expect(graph.locator(".react-flow__edge").first()).toBeAttached();
  const session = graph.locator('[data-id="IIET-1-3"].twin-graph-node');
  await session.press("Enter");
  const detail = page.getByRole("region", { name: "Resource details" });
  await expect(
    detail.getByRole("heading", { name: "Automata Theory and Computability" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Resources", exact: true }).click();
  await expect(graph).toHaveCount(0);
  await expect(
    detail.getByRole("heading", { name: "Automata Theory and Computability" }),
  ).toBeVisible();
});

test("faculty can switch to campus bookings and students see only their batch", async ({
  page,
}) => {
  await page.goto("/");
  const access = page.getByRole("navigation", { name: "Access portals" });
  await access.getByRole("link", { name: "Faculty", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Faculty sign-in" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Faculty", exact: true }).click();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My teaching timetable" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "List", exact: true }).click();
  await expect(
    page.getByText("Digital Signal Processing", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Campus timetable", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Campus timetable", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Timetable department").selectOption("ECE");
  await expect(
    page.getByText("Digital Signal Processing", { exact: true }),
  ).toHaveCount(3);
  await expect(
    page.getByRole("button", { name: "Add session", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await access.getByRole("link", { name: "Student", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Student sign-in" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Batch B1 demo", exact: true })
    .click();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My class timetable" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Demo week" }).click();
  const monday = page.locator(".weekgrid > div").first();
  await expect(monday.getByRole("button", { name: /Web Lab/ })).toContainText(
    "B1",
  );
  await expect(monday.getByRole("button", { name: /CN Lab/ })).toHaveCount(0);
  await expect(
    page.getByRole("group", { name: "Faculty timetable access" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await access.getByRole("link", { name: "Student", exact: true }).click();
  await page
    .getByRole("button", { name: "Batch B2 demo", exact: true })
    .click();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(page.getByText(/Section B · Batch B2/)).toBeVisible();
  await page.getByLabel("Timetable date").fill("2026-11-25");
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await expect(monday.getByRole("button", { name: /CN Lab/ })).toContainText(
    "B2",
  );
  await expect(monday.getByRole("button", { name: /Web Lab/ })).toHaveCount(0);
});

test("individual department accounts and account management use the same login page", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Login ID or institutional email")
    .fill("hod-ece@demo.omnis.example");
  await page.getByPlaceholder("Enter your password").fill("DemoECEHead!26");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Department teaching" }),
  ).toBeVisible();
  await expect(
    page.getByText("Digital Signal Processing", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(
    page.getByRole("button", { name: "Change password" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByRole("button", { name: "Admin", exact: true }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Find account").fill("hod-ece");
  await expect(
    page.getByText("ECE HOD (fictional)", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reset password", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "College events", exact: true }).click();
  await page.getByRole("button", { name: "Schedule event" }).click();
  await expect(
    page.getByRole("dialog", { name: "Schedule event" }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Organizing department")
      .getByRole("option", { name: "ECE" }),
  ).toHaveCount(1);
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await page.getByRole("button", { name: "Add session" }).click();
  const publish = page.getByRole("dialog", {
    name: "Publish teaching session",
  });
  const snapshot = await (await page.request.get("/api/dashboard")).json();
  await publish.getByLabel("Session ID").fill("UI-ATC");
  await publish.getByLabel("Subject").fill("Automata Theory and Computability");
  await publish.getByLabel("Department").selectOption("CSE");
  await publish.getByLabel("Assigned faculty").selectOption("f00");
  await publish.getByLabel("Section or batch").selectOption("c00");
  await publish.getByLabel("Room").selectOption("r0");
  await publish
    .getByLabel("Date", { exact: true })
    .fill(shiftDay(snapshot.anchor, 7));
  await publish.getByRole("button", { name: "Publish session" }).click();
  await expect(
    page.getByText("Session published", { exact: true }),
  ).toBeVisible();
});

test("resilience recalculates on date change and Analytics retains that date", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "HOD", exact: true }).click();
  const dashboardDate = page.getByLabel("Dashboard date");
  await expect(dashboardDate).toBeVisible();
  const dashboard = await page.request.get("/api/dashboard");
  const { anchor } = await dashboard.json();
  const tuesday = shiftDay(anchor, 1);
  const wednesday = shiftDay(anchor, 2);
  const overview = page.getByRole("region", { name: "Resilience overview" });
  const score = overview.locator('[aria-label^="Resilience score"]');
  await dashboardDate.fill(tuesday);
  await expect(overview).toContainText("38 scheduled sessions");
  const tuesdayResult = await page.request.get(
    "/api/analytics/resilience?day=" + tuesday,
  );
  await expect(tuesdayResult).toBeOK();
  const tuesdayReadiness = await tuesdayResult.json();
  expect(tuesdayReadiness).toMatchObject({ day: tuesday, sessions: 38 });
  await expect(score).toHaveAttribute(
    "aria-label",
    "Resilience score " + tuesdayReadiness.score + " out of 100",
  );
  await page.getByRole("button", { name: "Next dashboard day" }).click();
  await expect(dashboardDate).toHaveValue(wednesday);
  await expect(overview).toContainText("28 scheduled sessions");
  const wednesdayResult = await page.request.get(
    "/api/analytics/resilience?day=" + wednesday,
  );
  await expect(wednesdayResult).toBeOK();
  const wednesdayReadiness = await wednesdayResult.json();
  expect(wednesdayReadiness).toMatchObject({ day: wednesday, sessions: 28 });
  await expect(score).toHaveAttribute(
    "aria-label",
    "Resilience score " + wednesdayReadiness.score + " out of 100",
  );
  await overview.getByRole("button", { name: "Inspect" }).click();
  await expect(page.getByLabel("Analytics date")).toHaveValue(wednesday);
  await expect(
    page.getByRole("heading", { name: /Resilience score/ }),
  ).toBeVisible();
  await page.getByLabel("Analytics date").fill(shiftDay(anchor, 6));
  await expect(
    page.getByText("No scheduled sessions on this date."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /Resilience score/ }),
  ).toHaveCount(0);
});

test("IIET class timetable shows the lab rotation and the source course details", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Admin", exact: true }).click();
  await expect(
    page.getByText("Indian Institute of Engineering & Technology", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await page.getByRole("button", { name: "Demo week" }).click();
  const days = page.locator(".weekgrid > div");
  await expect(days).toHaveCount(7);
  const monday = days.nth(0);
  const friday = days.nth(4);
  await expect(
    monday.getByRole("button", { name: /Web Lab.*Semester V-B/ }),
  ).toContainText("B1");
  await expect(
    monday.getByRole("button", { name: /CN Lab.*Semester V-B/ }),
  ).toContainText("B2");
  await expect(
    friday.getByRole("button", { name: /Web Lab.*Semester V-B/ }),
  ).toContainText("B2");
  await expect(
    friday.getByRole("button", { name: /CN Lab.*Semester V-B/ }),
  ).toContainText("B1");
  await monday.getByRole("button", { name: /ATC.*Semester V-B/ }).click();
  const dialog = page.getByRole("dialog", {
    name: "Automata Theory and Computability",
  });
  await expect(dialog).toContainText("BCSPCC501");
  await expect(dialog).toContainText("Dr. Vikram Nair");
  await expect(dialog).toContainText("Room A126");
});
