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
  await page.context().addInitScript(() => { window.print = () => undefined; });
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

  await page.getByRole("button", { name: "导出札记" }).click();
  await expect(page.getByText("默认只保留重要内容")).toBeVisible();
  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: /Markdown/ }).click();
  await expect((await markdownDownload).suggestedFilename()).toMatch(/\.md$/);

  await page.getByRole("button", { name: "导出札记" }).click();
  await page.getByText("附上完整对话记录").click();
  const wordDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: /Word/ }).click();
  const downloadedWord = await wordDownload;
  await expect(downloadedWord.suggestedFilename()).toMatch(/\.docx$/);
  if (process.env.EXPORT_QA_DIR) await downloadedWord.saveAs(`${process.env.EXPORT_QA_DIR}/heart-note.docx`);

  await page.getByRole("button", { name: "导出札记" }).click();
  const printPagePromise = page.context().waitForEvent("page");
  await page.getByRole("button", { name: /PDF/ }).click();
  const printPage = await printPagePromise;
  await expect(printPage.getByRole("heading", { name: "我愿意承担的下一步" })).toBeVisible();
  await expect(printPage.getByRole("heading", { name: "完整对话记录" })).toBeVisible();
  if (process.env.EXPORT_QA_DIR) await printPage.pdf({ path: `${process.env.EXPORT_QA_DIR}/heart-note.pdf`, format: "A4", printBackground: true });
  await printPage.close();

  await page.getByRole("link", { name: "继续对话" }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${conversationId}`));

  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  await expect(page.getByTestId("remembered-context")).toContainText("AI产品经理");
  await expect(page.getByText("我记得你上次提到", { exact: false })).toBeVisible();

  await page.goto("/settings/memory");
  const memory = page.locator(".memory-settings-list article").first();
  await expect(memory).toContainText("AI产品经理");
  await memory.getByRole("button", { name: "修改", exact: true }).click();
  await memory.getByRole("textbox").fill("我希望转行做教育产品经理");
  await memory.getByRole("button", { name: "保存修改" }).click();
  await expect(memory).toContainText("教育产品经理");
  await memory.getByRole("button", { name: "暂停使用" }).click();
  await expect(memory).toContainText("已暂停使用");
  await memory.getByRole("button", { name: "恢复使用" }).click();
  await expect(memory).not.toContainText("已暂停使用");
});

test("安全响应后输入不锁死且可以恢复", async ({ page }, testInfo) => {
  const mobile = isMobile(testInfo);
  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  const input = page.getByLabel("你也可以自由输入");
  await input.fill("我现在就要自杀，马上会行动");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.getByText("我先暂停人物角色", { exact: false })).toBeVisible();
  await expect(page.getByTestId("safety-recovery-panel")).toBeVisible();
  await expect(page.getByLabel("安全支持中，你仍可以自由输入")).toBeEnabled();
  await page.getByRole("button", { name: "我现在安全", exact: true }).click();
  await expect(page.getByText("输入已经恢复", { exact: false })).toBeVisible();
  await expect(page.getByLabel("你也可以自由输入")).toBeEnabled();
});

test("日常负面表达不会误触发人物暂停", async ({ page }, testInfo) => {
  const mobile = isMobile(testInfo);
  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  const input = page.getByLabel("你也可以自由输入");
  await input.fill("这个项目让我很崩溃，但我想把问题一步步解决");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.locator(".message-card.assistant")).toHaveCount(2);
  await expect(page.getByTestId("safety-recovery-panel")).toHaveCount(0);
  await expect(page.getByText("我先暂停人物角色", { exact: false })).toHaveCount(0);
  await expect(input).toBeEnabled();
  await input.fill("我不想活了，只是想把这种感受完整说出来");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(page.locator(".message-card.assistant")).toHaveCount(3);
  await expect(page.getByTestId("safety-recovery-panel")).toHaveCount(0);
  await expect(input).toBeEnabled();
});

test("流式连接提前结束时给出安全重试并成功接续", async ({ page }, testInfo) => {
  const mobile = isMobile(testInfo);
  let interrupted = false;
  await page.route(/\/messages\/stream$/, async (route) => {
    if (interrupted) {
      await route.continue();
      return;
    }
    interrupted = true;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'event: chunk\ndata: {"text":"只到一半"}\n\n',
    });
  });

  await page.goto("/figures/confucius");
  await startConversation(page, mobile);
  const input = page.getByLabel("你也可以自由输入");
  await input.fill("请帮我分析这个选择");
  await page.getByRole("button", { name: "发送消息" }).click();
  const alert = page.locator(".status-banner.status-error");
  await expect(alert).toContainText("没有完整送达");
  await alert.getByRole("button", { name: "安全重试" }).click();
  await expect(page.locator(".message-card.assistant")).toHaveCount(2);
  await expect(alert).toHaveCount(0);
});

test("在世公众人物有显著身份和建议边界", async ({ page }) => {
  await page.goto("/figures/fengge-wangmingtianya");
  const notice = page.getByTestId("living-person-notice");
  await expect(notice).toContainText("非本人");
  await expect(notice).toContainText("非授权");
  await expect(notice).toContainText("投资");
  await expect(notice).toContainText("医疗");
});
