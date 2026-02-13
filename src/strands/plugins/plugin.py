"""Plugin protocol for Strands Agents.

Plugins are composable extensions that can register tools, hooks, and other configuration with an agent during
initialization.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..agent.agent import Agent


@runtime_checkable
class Plugin(Protocol):
    """Protocol for agent plugins.

    Plugins provide a composable way to extend agent functionality. They are passed to
    the Agent constructor via the ``plugins`` parameter and are initialized during agent
    setup.

    Example::

        class MyPlugin:
            name: str = "my-plugin"

            def init_plugin(self, agent: "Agent") -> None:
                # Register tools, hooks, etc.
                ...

        agent = Agent(plugins=[MyPlugin()])
    """

    @property
    def name(self) -> str:
        """The unique name of this plugin."""
        ...

    def init_plugin(self, agent: "Agent") -> None:
        """Initialize the plugin with the given agent.

        Called during Agent construction after the agent's core components (model, tool_registry,
        hooks, state, etc.) are initialized. Implementations should register tools, hooks, and
        perform any setup that requires the agent.

        Args:
            agent: The agent instance to extend.
        """
        ...
