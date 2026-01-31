"""ToolRegistry: Central registry for tool contracts.

Part of P1-TASK-06: Tool Registry + Schema Validation
Requirements: INV-01, P1-R01, P1-R18
"""


from autobiz.kernel.executor.tool_contract import ToolContract


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found in the registry.

    Attributes:
        tool_name: Name of the tool that was not found
        version: Version of the tool that was not found
    """

    def __init__(self, tool_name: str, version: str) -> None:
        """Initialize tool not found error.

        Args:
            tool_name: Name of the tool that was not found
            version: Version of the tool that was not found
        """
        super().__init__(f"Tool '{tool_name}' version '{version}' not found in registry")
        self.tool_name = tool_name
        self.version = version


class ToolRegistry:
    """Central registry for tool contracts.

    Provides:
    - Registration of tools with name and version
    - Lookup by name and version
    - Enforces INV-01 by providing schemas for validation
    """

    def __init__(self) -> None:
        """Initialize tool registry."""
        # Storage: {(name, version): ToolContract}
        self._tools: dict[tuple[str, str], ToolContract] = {}

    def register(self, tool: ToolContract) -> None:
        """Register a tool in the registry.

        Args:
            tool: ToolContract to register

        Raises:
            ValueError: If tool with same name/version already registered
        """
        key = (tool.name, tool.version)

        if key in self._tools:
            raise ValueError(f"Tool '{tool.name}' version '{tool.version}' already registered")

        self._tools[key] = tool

    def lookup(self, name: str, version: str) -> ToolContract:
        """Look up a tool by name and version.

        Args:
            name: Tool name
            version: Tool version (SemVer string)

        Returns:
            ToolContract for the requested tool

        Raises:
            ToolNotFoundError: If tool not found in registry
        """
        key = (name, version)

        if key not in self._tools:
            raise ToolNotFoundError(name, version)

        return self._tools[key]

    def list_tools(self) -> dict[tuple[str, str], ToolContract]:
        """List all registered tools.

        Returns:
            Dictionary mapping (name, version) to ToolContract
        """
        return self._tools.copy()
