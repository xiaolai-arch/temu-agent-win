"""端到端自测：以 MCP 客户端方式起 server 子进程，调核心工具链。"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=["server.py"],
                                   cwd=os.path.dirname(os.path.abspath(__file__)))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            r = await session.call_tool("edge_windows", {})
            print("edge_windows:", r.content[0].text)

            r = await session.call_tool("screenshot", {"name": "mcp-selftest"})
            imgs = [c for c in r.content if c.type == "image"]
            print("screenshot: image blocks =", len(imgs))

            r = await session.call_tool("write_report",
                {"task": "selftest", "ok": True,
                 "lines": ["MCP server 自测通过", "截图与报告链路 OK"]})
            print("write_report:", r.content[0].text)


asyncio.run(main())
