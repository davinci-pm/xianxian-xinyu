// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { useState } from "react";
import QuickReplies from "@/components/quick-replies";

function Fixture() {
  const [value, setValue] = useState("");
  return <><QuickReplies replies={["工作与方向"]} onChoose={setValue} /><label>输入框<input value={value} readOnly /></label></>;
}

afterEach(cleanup);

it("快捷回答只写入输入框，不自动提交", async () => {
  const user = userEvent.setup();
  render(<Fixture />);
  await user.click(screen.getByRole("button", { name: "工作与方向" }));
  expect(screen.getByLabelText("输入框")).toHaveProperty("value", "工作与方向");
});

