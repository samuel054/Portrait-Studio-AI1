import { expect, test, Page } from "@playwright/test";
const image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==";
const style = { id: "soft_lifestyle_illustration", name: "Soft Lifestyle Illustration", description: "Warm illustration.", category: "illustration", identity_priority: "high", background_modes: ["keep", "transparent"], output_types: ["social", "frame"] };
const secondStyle = { ...style, id: "premium_chibi", name: "Premium Chibi", category: "chibi", background_modes: ["replace"], output_types: ["gift", "sticker"] };
const candidates = ["A", "B"].map((id) => ({ id, rank: id === "A" ? 1 : 2, score: id === "A" ? 92 : 88, status: "pass", recommended: id === "A", content_type: "image/png", image_base64: image, filename: `${id}.png`, reasons: [] }));
async function mockApi(page: Page) {
  let selection: string | null = null;
  const requests: { path: string; body: string }[] = [];
  await page.route("**/api/backend/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/backend", "");
    const body = route.request().postData() ?? "";
    requests.push({ path, body });
    let data: object;
    if (path === "/v1/runtime") data = { ready: true, background_removal: false, checks: [] };
    else if (path === "/v1/styles") data = { styles: [style, secondStyle] };
    else if (path === "/v1/analyze") data = { analysis: { width: 1200, height: 1600, megapixels: 1.9 }, identity: { face_count: 1, guidance: ["Face is visible."] }, next_step: "style_selection" };
    else if (path === "/v1/portrait-jobs") data = { job: { id: "job-1", style_id: style.id, status: "generating", stage: "queued" } };
    else if (path.endsWith("/refine")) data = { job: { id: "job-2", style_id: style.id, status: "generating", stage: "refinement_queued" } };
    else if (path.startsWith("/v1/portrait-jobs/")) data = { job: { id: path.split("/").pop(), style_id: style.id, status: "awaiting_selection", stage: "candidates_ready", candidate_session_id: path.endsWith("job-2") ? "refined" : "session-1" } };
    else if (path.endsWith("/selection")) { selection = JSON.parse(body).candidate_id; data = { session: { id: path.split("/")[3], status: "selected", selected_candidate_id: selection, candidates } }; }
    else if (path.endsWith("/render")) { const format = JSON.parse(body).output_format; data = { render: { filename: `portrait.${format}`, content_type: `image/${format}`, image_base64: image, width: 1200, height: 1600 } }; }
    else if (path.startsWith("/v1/candidate-sessions/")) data = { session: { id: path.split("/").pop(), selected_candidate_id: selection, status: selection ? "selected" : "awaiting_selection", candidates } };
    else throw new Error(`Unexpected API call ${path}`);
    await route.fulfill({ json: data });
  });
  return requests;
}
async function upload(page: Page) {
  await page.locator('input[type="file"]').setInputFiles({ name: "portrait.png", mimeType: "image/png", buffer: Buffer.from(image, "base64") });
  await page.getByRole("button", { name: "Analyze photo", exact: true }).click();
  await expect(page.getByText("Your photo is ready", { exact: true })).toBeVisible();
}
async function generate(page: Page) {
  await upload(page);
  await page.getByRole("button", { name: "Soft Lifestyle Illustration", exact: false }).click();
  await page.getByRole("button", { name: "Generate portraits", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Which portrait feels like you?" })).toBeVisible();
}
test("compatible options, explicit selection, reselection, and every export format", async ({ page }) => {
  const requests = await mockApi(page); await page.goto("/"); await upload(page);
  await page.getByRole("button", { name: "Premium Chibi", exact: false }).click();
  await expect(page.getByRole("button", { name: "New studio setting", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Gift", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Generate portraits", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm selection", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Option A · Recommended", exact: false }).click();
  await page.getByRole("button", { name: "Confirm selection", exact: true }).click();
  await expect(page.getByRole("img", { name: "Portrait option A" })).toBeVisible();
  await page.getByRole("button", { name: "Option B", exact: false }).click();
  await expect(page.getByRole("button", { name: "Prepare download", exact: true })).not.toBeVisible();
  await page.getByRole("button", { name: "Confirm selection", exact: true }).click();
  for (const format of ["PNG", "JPEG", "WEBP"]) {
    await page.getByRole("button", { name: format, exact: true }).click();
    await page.getByRole("button", { name: "Prepare download", exact: true }).click();
    await expect(page.getByRole("button", { name: "Download portrait", exact: true })).toBeVisible();
  }
  expect(requests.filter((item) => item.path.endsWith("/feedback"))).toHaveLength(0);
  expect(requests.filter((item) => item.path.endsWith("/render")).map((item) => JSON.parse(item.body).output_format)).toEqual(["png", "jpeg", "webp"]);
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download portrait", exact: true }).click();
  expect((await downloadEvent).suggestedFilename()).toBe("portrait.webp");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
test("refinement returns through the evaluated candidate workflow and survives refresh", async ({ page }) => {
  const requests = await mockApi(page); await page.goto("/"); await generate(page);
  await page.getByRole("button", { name: "Option A · Recommended", exact: false }).click();
  await page.getByRole("button", { name: "Confirm selection", exact: true }).click();
  await page.getByRole("button", { name: "Create refined options", exact: true }).click();
  await expect.poll(() => requests.some((item) => item.path === "/v1/candidate-sessions/refined")).toBe(true);
  expect(requests.some((item) => item.path.startsWith("/v1/generations/"))).toBe(false);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Which portrait feels like you?" })).toBeVisible();
});
test("invalid replacement removes the previously accepted file", async ({ page }) => {
  await mockApi(page); await page.goto("/"); await upload(page);
  await page.locator('input[type="file"]').setInputFiles({ name: "wrong.txt", mimeType: "text/plain", buffer: Buffer.from("not a photo") });
  await expect(page.getByRole("alert").filter({ hasText: "Choose a JPG" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze photo", exact: true })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Generate portraits", exact: true })).not.toBeVisible();
});
