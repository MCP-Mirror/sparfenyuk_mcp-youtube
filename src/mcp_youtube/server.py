from __future__ import annotations

import inspect
import logging
import typing as t
from collections.abc import Sequence
from functools import cache

from mcp.server import Server
from mcp.types import (
    EmbeddedResource,
    GetPromptResult,
    ImageContent,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)
from pydantic.networks import AnyUrl

from . import tools

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = Server("mcp-youtube")


@cache
def enumerate_available_tools() -> t.Generator[tuple[str, Tool], t.Any, None]:
    for _, tool_args in inspect.getmembers(tools, inspect.isclass):
        if issubclass(tool_args, tools.ToolArgs) and tool_args != tools.ToolArgs:
            logger.debug("Found tool: %s", tool_args)
            description = tools.tool_description(tool_args)
            yield description.name, description


mapping: dict[str, Tool] = dict(enumerate_available_tools())


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    return [
        Prompt(
            name="YoutubeVideoSummary",
            description="Create a summary of the given video.",
            arguments=[PromptArgument(name="yt_url", description="URL of the video", required=True)],
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, args: dict[str, str] | None = None) -> GetPromptResult:
    """Get a prompt by name."""
    if name == "YoutubeVideoSummary":
        url = args.get("yt_url") if args else None
        if not url:
            raise ValueError("yt_url is required")
        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Create a summary of the video {url} using closed captions. Define key takeaways, "
                        "interesting facts, and the main topic of the video.",
                    ),
                ),
            ],
        )

    raise ValueError(f"Unknown prompt: {name}")


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return []


@app.read_resource()
async def get_resource(uri: AnyUrl) -> str | bytes:
    """Get a resource by URI."""
    return "{id: 1, name: 'test'}"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return list(mapping.values())


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """List available resources."""
    return []


@app.progress_notification()
async def progress_notification(pogress: str | int, p: float, s: float | None) -> None:
    """Progress notification."""


@app.call_tool()
async def call_tool(name: str, arguments: t.Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:  # noqa: ANN401
    """Handle tool calls for command line run."""

    if not isinstance(arguments, dict):
        raise TypeError("arguments must be dictionary")

    tool = mapping.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")

    try:
        args = tools.tool_args(tool, **arguments)
        return await tools.tool_runner(app.request_context.session, args)
    except Exception as e:
        logger.exception("Error running tool: %s", name)
        raise RuntimeError(f"Caught Exception. Error: {e}") from e


async def run_mcp_server() -> None:
    # Import here to avoid issues with event loops
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
