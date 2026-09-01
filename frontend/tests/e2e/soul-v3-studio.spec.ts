import path from "node:path";
import { expect, test } from "@playwright/test";

test("微信资料从 Soul V3 蒸馏到连续对话完整跑通", async ({ page }, testInfo) => {
  const login = await page.request.post("/api/backend/auth/login", {
    data: { invite_code: "E2E-SOUL-V3-001" },
  });
  expect(login.ok()).toBeTruthy();

  await page.goto("/studio/new");
  await page.getByLabel("心智分身的名称").fill("林舟");
  await page.getByRole("button", { name: /我熟悉的人/ }).click();
  await page.getByLabel("你们的关系").fill("长期朋友");
  await page.getByLabel("希望他陪你做什么").fill("在产品与人生取舍中复现他基于证据做实验的判断方式");
  await page.getByRole("button", { name: /继续上传资料/ }).click();

  await page.getByLabel("这批资料是什么").selectOption("chat");
  await page.getByLabel("目标说话人").fill("林舟");
  await page.getByLabel("资料时间范围").fill("2025");
  await page.locator('.upload-dropzone input[type="file"]').setInputFiles(
    path.resolve("../backend/tests/fixtures/wechat_soul_v3.txt"),
  );
  await expect(page.getByText("wechat_soul_v3.txt")).toBeVisible();
  await page.getByText("我确认有权在本次私人内测中使用这些资料", { exact: false }).click();
  await page.getByRole("button", { name: /继续校准/ }).click();

  await page.getByText("他最看重的三件事").locator("..").getByRole("textbox").fill(
    "诚实、证据、长期用户价值",
  );
  await page.getByText("最能说明他判断方式的一次选择").locator("..").getByRole("textbox").fill(
    "短期增长与长期留存冲突时，先验证真实使用信号。",
  );
  await page.getByText("他大概率绝不会做什么").locator("..").getByRole("textbox").fill(
    "不拿漂亮数字冒充价值，也不隐瞒坏消息。",
  );
  await page.getByText("哪种回答听起来聪明，却最不像他").locator("..").getByRole("textbox").fill(
    "只会空泛地让人继续努力，或者替别人保证结果。",
  );
  await page.getByRole("button", { name: /先做质量体检/ }).click();

  await expect(page.getByText("结构化蒸馏", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("真实盲测", { exact: true })).toBeVisible();
  await expect(page.getByText("真实人格相似度需通过留出集对话验证", { exact: false })).toBeVisible();
  if (process.env.VISUAL_QA) {
    await page.screenshot({ path: testInfo.outputPath("soul-v3-health.png"), fullPage: true });
  }
  await page.getByRole("button", { name: /开始灵魂蒸馏/ }).click();
  await expect(page.getByText("Soul V3 正在运行")).toBeVisible();
  await page.waitForURL(/\/me\?created=/);

  const persona = page.locator(".owned-persona-card").filter({ hasText: "林舟" }).first();
  await expect(persona).toContainText("仅自己可见");
  await persona.getByRole("button", { name: "开始对话" }).click();
  await page.waitForURL(/\/chat\//);
  const input = page.getByLabel("你也可以自由输入");
  await input.fill("短期收入和长期用户价值冲突时，我该怎么选？");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.locator(".message-card.assistant")).toHaveCount(2);
  await expect(page.getByText("按这些资料呈现的判断方式", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: /本段依据/ })).toBeVisible();
  if (process.env.VISUAL_QA) {
    await page.screenshot({ path: testInfo.outputPath("soul-v3-chat.png"), fullPage: true });
  }
});
