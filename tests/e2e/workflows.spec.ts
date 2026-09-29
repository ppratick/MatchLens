import { expect, test } from "@playwright/test";

test("synthetic review, corrections, undo/redo, pinned report, and restart", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore a synthetic demo" }).click();
  await expect(page.locator(".mini-stats strong").first()).toHaveText("14", { timeout: 60_000 });
  await expect(page.getByText("SYNTHETIC DEMO", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Play video", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause video", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pause video", exact: true }).click();
  await page.getByRole("button", { name: "Goal Blue XI" }).click();
  await page.getByLabel("Review status").selectOption("rejected");
  await page.getByRole("button", { name: "Save moment" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Undo review edit" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:1");
  await page.getByRole("button", { name: "Redo review edit" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Highlights & reports", exact: true }).click();
  await page.getByRole("button", { name: "Generate report" }).click();
  await expect(page.locator(".export-row")).toHaveCount(1, { timeout: 30_000 });
  const href = await page.getByRole("link", { name: "JSON", exact: true }).getAttribute("href");
  const report = await (await page.request.get(href!)).json();
  expect(report.statistics.score.away).toBe(0);
  expect(report.match.revision).toBe(report.statistics.revision);
  await page.reload();
  await page.getByRole("button", { name: /Recording preview SYNTHETIC DEMO/ }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Players", exact: true }).click();
  await expect(page.getByRole("button", { name: "Edit identity" })).toHaveCount(14);
});

test("setup and match creation retain local capability boundaries", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Local setup", exact: true }).click();
  await expect(page.getByText("Not required", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Match library/ }).click();
  await page.getByRole("button", { name: "New match", exact: true }).click();
  await page.getByLabel("Match title").fill("Screen review fixture");
  await page.getByRole("button", { name: "Create match" }).click();
  await expect(page.getByRole("heading", { name: "Screen review fixture" })).toBeVisible();
  await page.getByRole("button", { name: "Capture", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

async function generatedStream(page: import("@playwright/test").Page, method: "getDisplayMedia" | "getUserMedia") {
  await page.addInitScript(({ method }) => {
    Object.defineProperty(navigator.mediaDevices, method, { configurable: true, value: async () => {
      const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 360;
      const context = canvas.getContext("2d")!;
      setInterval(() => { context.fillStyle = "#274f35"; context.fillRect(0, 0, 640, 360); context.fillStyle = "#ef815a"; context.fillRect(100 + Math.sin(Date.now()/500)*20, 100, 20, 60); context.fillStyle = "white"; context.fillText("SYNTHETIC BROWSER CAPTURE · " + Date.now(), 20, 30); }, 33);
      return canvas.captureStream(30);
    }});
  }, { method });
}

test("label boxes and TV corners persist as review revisions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Recording preview SYNTHETIC DEMO/ }).click();
  await expect(page.getByRole("button", { name: "Label frame" })).toBeEnabled();
  await page.getByRole("button", { name: "Label frame" }).click();
  await page.getByRole("button", { name: "Use current boxes for manual review" }).click();
  await expect(page.getByLabel("Object identity")).toHaveCount(14);
  await page.getByLabel("Reviewed name").first().fill("Reviewed player");
  await page.getByRole("button", { name: "Save frame labels" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".video-overlay text").filter({ hasText: "Reviewed player" })).toBeVisible();
  await page.getByText("Source alignment & analysis versions", { exact: true }).click();
  await page.getByRole("button", { name: "Set television corners" }).click();
  const image = page.getByAltText("Select television picture corners");
  const rect = await image.boundingBox();
  for (const [x,y] of [[.1,.1],[.9,.1],[.9,.9],[.1,.9]]) await image.click({position:{x:rect!.width*x,y:rect!.height*y}});
  await page.getByRole("button", { name: "Save calibration" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("generated screen picker stream records playable segments on localhost", async ({ page }) => {
  await generatedStream(page, "getDisplayMedia");
  await page.goto("/");
  await page.getByRole("button", { name: "New match", exact: true }).click();
  await page.getByLabel("Match title").fill("Generated screen transport");
  await page.getByLabel("Recording profile").selectOption("screen");
  await page.getByRole("button", { name: "Create match" }).click();
  await page.getByRole("button", { name: "Capture", exact: true }).click();
  await page.getByRole("button", { name: "Choose screen or window" }).click();
  await expect(page.getByLabel("Incoming screen preview")).toBeVisible();
  await expect(page.getByText("no audio track supplied", { exact: false })).toBeVisible();
  await expect(page.locator(".job-inline")).toContainText("Recording", {timeout:20000});
  await page.waitForTimeout(6500);
  await page.getByRole("button", { name: "Finish screen recording", exact: true }).first().click();
  await expect(page.getByText(/Received bytes finalized/)).toBeVisible({timeout:30000});
  await page.keyboard.press("Escape");
  await expect(page.locator(".segment-select option")).not.toHaveCount(0);
  await page.getByRole("button", { name: "Play video", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause video", exact: true })).toBeVisible();
});

test("generated phone camera aligns TV and finalizes received original", async ({ page, request }) => {
  const session=await (await request.get("/api/session")).json();
  const headers={"x-matchlens-token":session.token};
  const match=await (await request.post("/api/matches",{headers,data:{title:"Generated phone transport",profile:"phone_tv"}})).json();
  const pair=await (await request.post(`/api/matches/${match.id}/pair`,{headers})).json();
  await generatedStream(page,"getUserMedia");
  await page.goto(`http://127.0.0.1:8878/${pair.fragment}`);
  await page.getByRole("button",{name:"Start camera preview"}).click();
  await expect(page.locator("#preview")).toBeVisible();
  const rect=await page.locator("#preview").boundingBox();
  for(const [x,y] of [[.1,.1],[.9,.1],[.9,.9],[.1,.9]])await page.locator("#preview").click({position:{x:rect!.width*x,y:rect!.height*y}});
  await page.getByRole("button",{name:"Save alignment & record"}).click();
  await expect(page.locator("#status")).toContainText("Sending",{timeout:10000});
  await expect(page.locator("#recording")).toContainText(/committed playable segments/);
  await page.waitForTimeout(6500);
  await page.getByRole("button",{name:"Finish recording"}).click();
  await expect(page.locator("#status")).toContainText("finalized on Mac",{timeout:30000});
  await expect.poll(async()=>{const d=await (await request.get(`/api/matches/${match.id}`)).json();return d.sources[0].segments.length;}).toBeGreaterThan(0);
  const detail=await (await request.get(`/api/matches/${match.id}`)).json();
  expect(detail.review.television[detail.sources[0].id].corners).toHaveLength(4);
  const media=await request.get(`/media/${match.id}/${detail.sources[0].id}?segment=${detail.sources[0].segments[0].id}`,{headers:{Range:"bytes=0-99"}});
  expect(media.status()).toBe(206);
});
