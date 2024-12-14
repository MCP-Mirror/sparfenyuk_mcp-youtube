import asyncio

from typer import Context, Typer

app = Typer()


@app.callback(invoke_without_command=True)
def _run(ctx: Context) -> None:
    if ctx.invoked_subcommand is None:
        # This will run if no subcommand is specified
        run()


@app.command()
def run() -> None:
    """Run the mcp-youtube server."""
    from .server import run_mcp_server

    asyncio.run(run_mcp_server())
