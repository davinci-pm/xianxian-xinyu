// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { useState } from "react";
import Drawer from "@/components/drawer";

function DrawerFixture() {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>查看引用</button><Drawer title="引用" open={open} onClose={() => setOpen(false)}><p>来源内容</p></Drawer></>;
}

afterEach(cleanup);

describe("引用抽屉", () => {
  it("关闭后把焦点还给触发按钮", async () => {
    const user = userEvent.setup();
    render(<DrawerFixture />);
    const opener = screen.getByRole("button", { name: "查看引用" });
    await user.click(opener);
    expect(screen.getByRole("dialog")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "关闭面板" }));
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});
