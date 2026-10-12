/** node tests/browser_smoke.mjs。使用本机 Chrome；Linux 可设置 BROWSER_EXECUTABLE。
 * 产品 CRUD 使用真实 API；问数事件固定模拟，以测试页面且不额外调用模型。
 * 会话和收藏仅清理本脚本创建的记录，截图放在 tests/artifacts（不提交）。
 */
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import assert from "node:assert/strict";
const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const base = process.env.TEST_BASE_URL || "http://localhost:8080";
const executablePath = process.env.BROWSER_EXECUTABLE || (existsSync("C:/Program Files/Google/Chrome/Application/chrome.exe") ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : undefined);
const browser = await chromium.launch({ executablePath, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
const created = [];
const artifacts = new URL("./artifacts/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const http = async (method, path, data) => {
  const result = await context.request.fetch(base + path, { method, data });
  assert.ok(result.ok(), `${method} ${path}: ${result.status()}`);
  return result.status() === 204 ? null : result.json();
};
try {
  await page.route("**/api/sessions", async route => {
    if (route.request().method() === "POST") {
      const response = await route.fetch(); const data = await response.json(); created.push(data.id);
      await route.fulfill({ response });
    } else await route.continue();
  });
  await page.goto(base);
  await page.getByRole("heading", { name: "我是 AI 问数助手" }).waitFor();
  await page.screenshot({ path: new URL("welcome.png", artifacts).pathname.replace(/^\/([A-Z]:)/, "$1"), fullPage: true });
  await page.getByRole("link", { name: "应用配置", exact: true }).click();
  await page.getByRole("button", { name: "配置对话开场白" }).click();
  await page.getByLabel("开场白文案").fill("浏览器验收：欢迎使用 AI 问数");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await page.reload();
  await page.getByRole("link", { name: "智能问数", exact: true }).click();
  await page.getByText("浏览器验收：欢迎使用 AI 问数", { exact: true }).waitFor();
  console.log("[PASS] App settings save / refresh / welcome rendering");
  await page.getByRole("button", { name: "展开或收起历史记录" }).click();
  const refreshed = page.waitForResponse(r => r.url().endsWith("/api/sessions?days=30") && r.request().method() === "GET");
  await page.getByRole("button", { name: "开启新对话" }).click();
  await refreshed;
  const sessionId = created.at(-1);
  assert.ok(sessionId);
  await page.getByRole("button", { name: "操作会话：新对话", exact: true }).first().click();
  await page.getByRole("button", { name: "重命名", exact: true }).click();
  await page.getByLabel("会话标题").fill("浏览器验收会话");
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await page.getByRole("button", { name: "操作会话：浏览器验收会话", exact: true }).click();
  const pinned = page.waitForResponse(r => r.url().endsWith(`/api/sessions/${sessionId}`) && r.request().method() === "PATCH");
  await page.getByRole("button", { name: "置顶", exact: true }).click();
  await pinned;
  assert.equal((await http("GET", `/api/sessions/${sessionId}`)).pinned, true);
  console.log("[PASS] Actual session create / rename / pin APIs through UI");
  const question = "浏览器验收：2026年商业目标TOP5，金额单位万元";
  const units = [["北京代表处",7950,1200],["上海代表处",7070,980],["浙江代表处",6460,860],["江苏代表处",5560,720],["山东代表处",4090,650]];
  const rows = units.map(([经营单元,商业目标,商解目标]) => ({经营单元,商业目标,商解目标}));
  const columns = [{key:"经营单元",label:"经营单元",kind:"dimension",unit:"",additive:false},{key:"商业目标",label:"商业目标",kind:"metric",unit:"万元",additive:true},{key:"商解目标",label:"商解目标",kind:"metric",unit:"万元",additive:true}];
  const result = {type:"result",data:rows,presentation:{query:question,sql:"SELECT ... LIMIT 5",tables:["fact_target_yearly","dim_business_unit"],conditions:["target_year = 2026"],metric_definitions:[],columns,statistics:[{key:"商业目标",label:"商业目标",unit:"万元",count:5,total:31130,average:6226,max:7950,min:4090},{key:"商解目标",label:"商解目标",unit:"万元",count:5,total:4410,average:882,max:1200,min:650}],row_count:5,result_scope:"本次返回的五个经营单元",data_dates:{},chart:{type:"bar",dimension:"经营单元",metrics:["商业目标","商解目标"]},suggestions:["2026年商业目标TOP5明细","2026年目标最高与最低值对比","2026年收入按产品线拆分"]},elapsed_ms:600,model_name:"browser-test"};
  let mockIndex = 0;
  await page.route("**/api/query", async route => {
    const request = route.request().postDataJSON();
    assert.equal(request.session_id, sessionId);
    const timestamp = new Date().toISOString();
    const user = {id:`test-user-${mockIndex}`,session_id:sessionId,role:"user",content:request.query,status:"done",created_at:timestamp,payload:null};
    const assistant = {id:`test-answer-${mockIndex++}`,session_id:sessionId,role:"assistant",content:"正在处理问题",status:"streaming",created_at:timestamp,payload:null};
    const events = [{type:"conversation",session_id:sessionId,user,assistant},{type:"progress",step:"生成SQL",status:"success"},{...result,message_id:assistant.id}];
    await route.fulfill({ status:200, contentType:"text/event-stream", body:events.map(e => `data: ${JSON.stringify(e)}\n\n`).join("") });
  });
  await page.getByLabel("问题输入框").fill(question);
  await page.getByRole("button", { name:"发送问题" }).click();
  await page.getByRole("heading", { name:"数据可视化" }).waitFor();
  await page.getByRole("img", { name:"查询结果柱状图" }).waitFor();
  await page.locator("canvas").first().waitFor();
  assert.ok((await page.locator(".answer-card").innerText()).includes("4,410"));
  await page.getByRole("button", { name:"分析过程" }).click();
  await page.getByText("SELECT ... LIMIT 5", { exact:true }).waitFor();
  await page.screenshot({ path:new URL("answer.png",artifacts).pathname.replace(/^\/([A-Z]:)/,"$1"),fullPage:true });
  await page.getByRole("button", { name:"收藏问题",exact:true }).click();
  await page.getByRole("status").filter({hasText:"问题已收藏"}).waitFor();
  const favorite = (await http("GET","/api/favorites")).find(f=>f.question===question);
  assert.ok(favorite);
  await http("DELETE",`/api/favorites/${favorite.id}`);
  await page.getByRole("button",{name:"编辑问题",exact:true}).click();
  await page.getByLabel("编辑问题").fill("编辑后的测试问题");
  await page.getByRole("button",{name:"取消",exact:true}).click();
  assert.equal(await page.locator(".user-bubble").first().innerText(),question);
  console.log("[PASS] SSE rendering / statistics / chart / favorite / edit cancel");
  await page.getByRole("link",{name:"应用配置",exact:true}).click();
  await page.getByRole("button",{name:"配置模型配置"}).click();
  await page.getByRole("heading",{name:"应用模型设置"}).waitFor();
  await page.getByLabel("智能问数模型").selectOption("__add__");
  await page.getByRole("dialog",{name:"新增模型"}).waitFor();
  assert.ok(await page.getByRole("button",{name:"添加",exact:true}).isDisabled());
  await page.getByRole("button",{name:"取消",exact:true}).click();
  await page.getByRole("link",{name:"回复校对",exact:true}).click();
  await page.getByRole("heading",{name:"回复校对",exact:true}).waitFor();
  await page.getByLabel("搜索反馈问题").fill("不存在的验收问题");
  await page.getByText("暂无反馈数据",{exact:true}).waitFor();
  await page.screenshot({path:new URL("feedbacks.png",artifacts).pathname.replace(/^\/([A-Z]:)/,"$1"),fullPage:true});
  console.log("[PASS] Model page / add dialog / feedback search");
  await page.getByRole("link",{name:"智能问数",exact:true}).click();
  await page.getByRole("button",{name:"展开或收起历史记录"}).click();
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(() => Math.abs(document.querySelector('.main-sidebar').getBoundingClientRect().width - 60) < 1);
  await page.screenshot({path:new URL("mobile.png",artifacts).pathname.replace(/^\/([A-Z]:)/,"$1"),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);
  console.log("[PASS] Mobile viewport / no browser exceptions");
} finally {
  for(const id of created) await http("DELETE",`/api/sessions/${id}`).catch(()=>{});
  await browser.close();
}
