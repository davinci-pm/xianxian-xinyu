import { expect, test, type Page, type TestInfo } from "@playwright/test";

function isMobile(testInfo: TestInfo) { return testInfo.project.name.includes("mobile"); }

async function startConversation(page: Page, mobile: boolean) {
  await (mobile ? page.locator(".mobile-start-bar button") : page.locator(".figure-start")).click();
  await page.waitForURL(/\/chat\//);
  await expect(page.getByText("最近有什么事", { exact: false })).toBeVisible();
}

test("首页筛选可以清空并恢复人物", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("persona-card-confucius")).toBeVisible();
  await page.getByPlaceholder("搜索人物、思想或话题").fill("孔子");
  await expect(page.locator(".persona-card")).toHaveCount(1);
  await page.getByTestId("clear-filters").click();
  await expect(page.getByPlaceholder("搜索人物、思想或话题")).toHaveValue("");
  await expect(page.locator(".persona-card")).toHaveCount(9);
});

test("思想路径到札记和继续对话的完整主链路", async ({ page }, testInfo) => {
  const mobile = isMobile(testInfo);
  await page.goto("/");
  await page.getByLabel("此刻，什么事情最困扰你？").fill("我想换工作，但担心影响家人，也害怕自己选错");
  await page.getByRole("button", { name: "从当前困惑开始" }).click();
  await expect(page).toHaveURL(/\/paths\?concern=/);
  await page.getByRole("button", { name: "更想做出一个决定" }).click();
  await page.getByRole("button", { name: "迷茫", exact: true }).click();
  await page.getByRole("button", { name: "看看谁适合我" }).click();
  const confuciusRecommendation = page.locator(".path-persona-card").filter({ hasText: "孔子" });
  await expect(confuciusRecommendation).toBeVisible();
  await confuciusRecommendation.getByRole("link", { name: "先了解 TA" }).click();
  await expect(page.getByRole("heading", { name: "孔子", exact: true })).toBeVisible();
  await expect(page.getByText("TA 可能会这样主动开始")).toBeVisible();
  await startConversation(page, mobile);

  const input = page.getByLabel("你也可以自由输入");
  const quick = page.locator(".quick-replies button").first();
  const quickText = await quick.innerText();
  await quick.click();
  await expect(input).toHaveValue(quickText);
  await expect(page.locator(".message-card.assistant")).toHaveCount(1);

  await input.fill("我希望转行做AI产品经理，但担心失败");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.locator(".message-card.assistant")).toHaveCount(2);
  await expect(page.getByTestId("memory-candidate")).toBeVisible();
  await page.getByTestId("memory-candidate").getByRole("button", { name: "记住" }).click();
  await expect(page.getByTestId("memory-candidate")).toHaveCount(0);

  if (mobile) {
    await page.getByRole("button", { name: "打开对话菜单" }).click();
    await page.getByRole("button", { name: "查看引用" }).click();
  } else {
    await page.getByRole("button", { name: "打开全部引用" }).click();
  }
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "关闭面板" }).click();

  const conversationId = page.url().split("/").pop();
  if (mobile) await page.goto(`/notes?conversation=${conversationId}`);
  else await page.getByRole("link", { name: "结束并生成心语札记" }).click();
  await page.waitForURL(/\/notes\/.+/);
  await expect(page.getByLabel("札记标题")).toBeVisible();
  await page.getByLabel("札记标题").fill("我愿意承担的下一步");
  await page.waitForTimeout(750);
  await page.reload();
  await expect(page.getByLabel("札记标题")).toHaveValue("我愿意承担的下一步");
  await page.context().setOffline(true);
  await page.getByLabel("札记正文").fill("## 离线时写下的一步\n\n明天先和家人谈清楚我的顾虑。");
  await expect(page.getByText("离线草稿已存本机")).toBeVisible();
  await page.waitForTimeout(750);
  await page.context().setOffline(false);
  await page.reload();
  await expect(page.getByLabel("札记正文")).toContainText("明天先和家人谈清楚");
  await page.getByRole("link", { name: "继续对话" }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${conversationId}`));

  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  await expect(page.getByTestId("remembered-context")).toContainText("AI产品经理");
  await expect(page.getByText("我记得你上次提到", { exact: false })).toBeVisible();
});

test("安全响应后输入不锁死且可以恢复", async ({ page }, testInfo) => {
  const mobile = isMobile(testInfo);
  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  const input = page.getByLabel("你也可以自由输入");
  await input.fill("我不想活了");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.getByText("我先暂停人物角色", { exact: false })).toBeVisible();
  await expect(page.getByTestId("safety-recovery-panel")).toBeVisible();
  await expect(page.getByLabel("安全支持中，你仍可以自由输入")).toBeEnabled();
  await page.getByRole("button", { name: "我现在安全", exact: true }).click();
  await expect(page.getByText("输入已经恢复", { exact: false })).toBeVisible();
  await expect(page.getByLabel("你也可以自由输入")).toBeEnabled();
});

test("在世公众人物有显著身份和建议边界", async ({ page }) => {
  await page.goto("/figures/fengge-wangmingtianya");
  const notice = page.getByTestId("living-person-notice");
  await expect(notice).toContainText("非本人");
  await expect(notice).toContainText("非授权");
  await expect(notice).toContainText("投资");
  await expect(notice).toContainText("医疗");
});
