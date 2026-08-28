"""Adapter exposing an existing search backend through Tool Runtime.

The adapter does not implement retrieval itself. It wraps an existing
search callable so research/search semantics remain owned by the current
search provider layer.
"""

from __future__ import annotations

from inspect import isawaitable
from typing import Any, Awaitable, Callable

from services.tool_runtime import (
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
)


SearchCallable = Callable[
    [str, int],
    Any | Awaitable[Any],
]


def build_search_tool_definition(
    *,
    name: str = "web_search",
    source: str = "search",
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=(
            "Search external sources for information "
            "relevant to the current research task."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                required=True,
                description="Search query",
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                required=False,
                description=(
                    "Maximum number of search results"
                ),
            ),
        ],
        source=source,
        read_only=True,
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                },
            },
            "required": [
                "query",
            ],
        },
    )


class SearchToolAdapter:
    """Register an existing search callable as a runtime tool."""

    def __init__(
        self,
        *,
        search: SearchCallable,
        tool_name: str = "web_search",
        default_max_results: int = 5,
        source: str = "search",
    ) -> None:
        if default_max_results < 1:
            raise ValueError(
                "default_max_results must be positive"
            )

        self.search = search
        self.tool_name = tool_name
        self.default_max_results = (
            default_max_results
        )
        self.source = source

    def definition(
        self,
    ) -> ToolDefinition:
        return build_search_tool_definition(
            name=self.tool_name,
            source=self.source,
        )

    def register(
        self,
        registry: ToolRegistry,
    ) -> ToolDefinition:
        definition = self.definition()

        async def handler(
            arguments: dict[str, Any],
        ) -> Any:
            query = str(
                arguments["query"]
            ).strip()

            if not query:
                raise ValueError(
                    "Search query must not be empty"
                )

            max_results = int(
                arguments.get(
                    "max_results",
                    self.default_max_results,
                )
            )

            if max_results < 1:
                raise ValueError(
                    "max_results must be positive"
                )

            result = self.search(
                query,
                max_results,
            )

            if isawaitable(result):
                result = await result

            return result

        registry.register(
            definition=definition,
            handler=handler,
        )

        return definition
