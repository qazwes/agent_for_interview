/** 模拟并行失败、异常断流和主动停止；不调用模型、不写产品数据库。 */
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import assert from "node:assert/strict";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const base = process.env.TEST_BASE_URL || "http://localhost:8080";
const executablePath = process.env.BROWSER_EXECUTABLE || (existsSync("C:/Program Files/Google/Chrome/Application/chrome.exe") ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : undefined);
const browser = await chromium.launch({ executablePath, headless: true });
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
const timestamp = new Date().toISOString();
const conversation = { id: "failure-test-session", title: "异常状态验收", pinned: false, created_at: timestamp, updated_at: timestamp };
const oldSteps = [{ step: "抽取关键词", status: "success" }, { step: "过滤表信息", status: "running" }, { step: "过滤指标信息", status: "error" }];
const legacyMessages = [
  { id: "legacy-user", session_id: conversation.id, role: "user", content: "并行失败", status: "done", created_at: timestamp, payload: null },
  { id: "legacy-answer", session_id: conversation.id, role: "assistant", content: "查询失败。", status: "error", created_at: timestamp, payload: { steps: oldSteps, error: "模拟上游 502" } },
];

try {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const data = path === "/api/sessions" ? [conversation] : path === `/api/sessions/${conversation.id}` ? { ...conversation, messages: legacyMessages } : [];
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.addInitScript(({ sessionId }) => {
    const realFetch = window.fetch.bind(window);
    let index = 0;
    window.__queryCancelled = 0;
    window.fetch = async (input, options) => {
      if (!String(input).endsWith("/api/query")) return realFetch(input, options);
      const { query } = JSON.parse(options.body);
      const stamp = new Date().toISOString();
      const shared = { session_id: sessionId, created_at: stamp, payload: null };
      const user = { ...shared, id: `user-${index}`, role: "user", content: query, status: "done" };
      const assistant = { ...shared, id: `answer-${index++}`, role: "assistant", content: "正在处理…", status: "streaming", reply_to_id: user.id };
      const events = [
        { type: "conversation", session_id: sessionId, user, assistant },
        { type: "progress", step: "抽取关键词", status: "success" },
        { type: "progress", step: "过滤表信息", status: "running" },
        { type: "progress", step: "过滤指标信息", status: "running" },
      ];
      if (query === "并行失败") events.push(
        { type: "progress", step: "过滤指标信息", status: "error" },
        { type: "error", message: "模拟上游 502" },
        // 终态后的迟到事件必须忽略，不能重启转圈或覆盖错误。
        { type: "progress", step: "过滤表信息", status: "running" },
        { type: "result", data: [] },
      );
      const encoder = new TextEncoder();
      let onAbort;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join("")));
          if (query === "断流") controller.close();
          else {
            onAbort = () => controller.error(new DOMException("Aborted", "AbortError"));
            options.signal.addEventListener("abort", onAbort, { once: true });
          }
        },
        cancel() {
          window.__queryCancelled++;
          if (onAbort) options.signal.removeEventListener("abort", onAbort);
        },
      });
      // 502 场景故意保持连接不关闭，验证收到 error 后客户端立即释放读流。
      return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
    };
  }, { sessionId: conversation.id });

  const send = async text => {
    await page.getByLabel("问题输入框").fill(text);
    await page.getByRole("button", { name: "发送问题", exact: true }).click();
  };
  const assertNoRunning = async card => {
    await page.waitForFunction(() => !!document.querySelector('button[aria-label="发送问题"]'));
    assert.ok(await page.getByRole("button", { name: "重新发送问题", exact: true }).last().isEnabled());
    assert.equal(await card.locator(".spin, .analysis-step.running").count(), 0);
  };

  await page.goto(base);
  await page.getByRole("heading", { name: "我是 AI 问数助手" }).waitFor();
  await send("并行失败");
  let card = page.locator(".answer-card").last();
  await card.getByRole("alert").filter({ hasText: "模拟上游 502" }).waitFor();
  await page.getByRole("button", { name: "发送问题", exact: true }).waitFor();
  await card.getByRole("button", { name: "分析过程" }).click();
  await card.getByText("过滤表信息（已中断）", { exact: true }).waitFor();
  assert.equal(await card.locator(".analysis-step.error").innerText(), "过滤指标信息");
  assert.equal(await card.locator(".analysis-step.success").innerText(), "抽取关键词");
  await assertNoRunning(card);
  assert.equal(await page.evaluate(() => window.__queryCancelled), 1);
  console.log("[PASS] Parallel failure / immediate stream close / late events ignored");

  await page.reload();
  card = page.locator(".answer-card").last();
  await card.getByRole("alert").filter({ hasText: "模拟上游 502" }).waitFor();
  await card.getByRole("button", { name: "分析过程" }).click();
  await card.getByText("过滤表信息（已中断）", { exact: true }).waitFor();
  await assertNoRunning(card);
  console.log("[PASS] Legacy failed history restored without running steps");

  await page.getByRole("button", { name: "重新发送问题", exact: true }).last().click();
  await page.waitForFunction(() => document.querySelectorAll('.answer-card').length === 2);
  card = page.locator(".answer-card").last();
  await card.getByRole("alert").filter({ hasText: "模拟上游 502" }).waitFor();
  await assertNoRunning(card);
  assert.equal(await page.locator(".user-bubble").count(), 2);
  console.log("[PASS] Manual resend preserves original messages");

  await send("断流");
  card = page.locator(".answer-card").last();
  await card.getByRole("alert").filter({ hasText: "没有收到查询结果" }).waitFor();
  await card.getByRole("button", { name: "分析过程" }).click();
  assert.equal(await card.locator(".analysis-step.cancelled").count(), 2);
  await assertNoRunning(card);
  console.log("[PASS] Unexpected EOF closes all unfinished steps");

  await send("停止");
  card = page.locator(".answer-card").last();
  await card.getByRole("button", { name: "分析过程" }).click();
  await card.locator(".analysis-step.running").first().waitFor();
  await page.getByRole("button", { name: "停止查询", exact: true }).click();
  await card.getByText("已停止本次查询。", { exact: true }).waitFor();
  assert.equal(await card.locator(".analysis-step.cancelled").count(), 2);
  await assertNoRunning(card);
  assert.deepEqual(errors, []);
  console.log("[PASS] User stop closes all unfinished steps / no page exceptions");
} finally {
  await browser.close();
}
