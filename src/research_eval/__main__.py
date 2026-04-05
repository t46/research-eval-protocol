"""Entry point for the Research Evaluation Protocol MCP server."""

from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
