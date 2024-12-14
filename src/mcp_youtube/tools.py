from __future__ import annotations

import json
import logging
import sys
import typing as t
from functools import singledispatch
from urllib.parse import parse_qs, urlparse

from mcp.server.session import ServerSession
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)
from pydantic import BaseModel, ConfigDict
from xdg_base_dirs import xdg_cache_home
from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# How to add a new tool:
#
# 1. Create a new class that inherits from ToolArgs
#    ```python
#    class NewTool(ToolArgs):
#        """Description of the new tool."""
#        pass
#    ```
#    Attributes of the class will be used as arguments for the tool.
#    The class docstring will be used as the tool description.
#
# 2. Implement the tool_runner function for the new class
#    ```python
#    @tool_runner.register
#    async def new_tool(args: NewTool) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
#        pass
#    ```
#    The function should return a sequence of TextContent, ImageContent or EmbeddedResource.
#    The function should be async and accept a single argument of the new class.
#
# 3. Done! Restart the client and the new tool should be available.


class ToolArgs(BaseModel):
    model_config = ConfigDict()


@singledispatch
async def tool_runner(
    args,  # noqa: ANN001
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    raise NotImplementedError(f"Unsupported type: {type(args)}")


def tool_description(args: type[ToolArgs]) -> Tool:
    return Tool(
        name=args.__name__,
        description=args.__doc__,
        inputSchema=args.model_json_schema(),
    )


def tool_args(tool: Tool, *args, **kwargs) -> ToolArgs:  # noqa: ANN002, ANN003
    return sys.modules[__name__].__dict__[tool.name](*args, **kwargs)


## Tools ##

### Download close captions from YouTube video ###


class DownloadClosedCaptions(ToolArgs):
    """Download closed captions from YouTube video."""

    video_url: str


def _parse_youtube_url(url: str) -> str | None:
    """
    Parse a YouTube URL and extract the video ID from the v= parameter.

    Args:
        url (str): YouTube URL in various formats

    Returns:
        str: Video ID if found, None otherwise

    Examples:
        >>> parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123")
        'dQw4w9WgXcQ'
    """

    # Handle youtu.be format
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]

    # Handle regular youtube.com format
    try:
        parsed_url = urlparse(url)
        if "youtube.com" in parsed_url.netloc:
            params = parse_qs(parsed_url.query)
            if "v" in params:
                return params["v"][0]
    except:  # noqa: E722, S110
        pass

    return None


@tool_runner.register
async def download_closed_captions(
    args: DownloadClosedCaptions,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    transcripts_dir = xdg_cache_home() / "mcp-youtube" / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    video_id = _parse_youtube_url(args.video_url)
    if not video_id:
        raise ValueError(f"Unrecognized YouTube URL: {args.video_url}")

    if not transcripts_dir.joinpath(f"{video_id}.json").exists():
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        if not transcript or not isinstance(transcript, list):
            raise ValueError("No transcript found for the video.")

        json_data = json.dumps(transcript, indent=None)
        transcripts_dir.joinpath(f"{video_id}.json").write_text(json_data)

    else:
        json_data = transcripts_dir.joinpath(f"{video_id}.json").read_text()
        transcript = json.loads(json_data)

    content = " ".join([line["text"] for line in transcript])

    return [
        TextContent(
            type="text",
            text=content,
        ),
    ]
