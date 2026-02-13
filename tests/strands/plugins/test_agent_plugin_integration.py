"""Tests for Agent integration with the Plugin protocol."""

import unittest.mock

from strands import Agent
from strands.plugins.plugin import Plugin


class TestAgentPluginIntegration:
    def test_agent_calls_init_plugin(self):
        """Test that Agent calls init_plugin on each plugin during construction."""
        plugin = unittest.mock.MagicMock(spec=Plugin)
        plugin.name = "test-plugin"

        agent = Agent(plugins=[plugin])

        plugin.init_plugin.assert_called_once_with(agent)

    def test_agent_calls_multiple_plugins(self):
        """Test that Agent calls init_plugin on multiple plugins in order."""
        plugin1 = unittest.mock.MagicMock(spec=Plugin)
        plugin1.name = "plugin-1"
        plugin2 = unittest.mock.MagicMock(spec=Plugin)
        plugin2.name = "plugin-2"

        agent = Agent(plugins=[plugin1, plugin2])

        plugin1.init_plugin.assert_called_once_with(agent)
        plugin2.init_plugin.assert_called_once_with(agent)

    def test_agent_without_plugins(self):
        """Test that Agent works fine without plugins."""
        agent = Agent()
        # Should not raise
        assert agent is not None

    def test_agent_with_empty_plugins_list(self):
        """Test that Agent works with an empty plugins list."""
        agent = Agent(plugins=[])
        # Should not raise
        assert agent is not None

    def test_plugins_initialized_after_hooks(self):
        """Test that plugins are initialized after hooks are set up."""
        call_order = []

        class OrderTrackingPlugin:
            name = "order-tracker"

            def init_plugin(self, agent):
                # Verify hooks registry exists
                assert hasattr(agent, "hooks")
                assert hasattr(agent, "tool_registry")
                assert hasattr(agent, "state")
                call_order.append("plugin_init")

        plugin = OrderTrackingPlugin()
        Agent(plugins=[plugin])

        assert "plugin_init" in call_order

    def test_plugin_can_register_tools(self):
        """Test that a plugin can register tools during init_plugin."""
        from strands.tools.decorator import tool

        @tool
        def my_custom_tool(value: str) -> str:
            """A custom tool.

            Args:
                value: A value.
            """
            return value

        class ToolPlugin:
            name = "tool-plugin"

            def init_plugin(self, agent):
                agent.tool_registry.register_tool(my_custom_tool)

        agent = Agent(plugins=[ToolPlugin()])

        assert "my_custom_tool" in agent.tool_names

    def test_plugin_can_register_hooks(self):
        """Test that a plugin can register hooks during init_plugin."""
        from strands.hooks import AgentInitializedEvent, BeforeInvocationEvent, HookProvider, HookRegistry

        callback_called = []

        class HookPlugin:
            name = "hook-plugin"

            def init_plugin(self, agent):
                class _Hooks(HookProvider):
                    def register_hooks(self, registry, **kwargs):
                        registry.add_callback(BeforeInvocationEvent, lambda event: callback_called.append(True))

                agent.hooks.add_hook(_Hooks())

        agent = Agent(plugins=[HookPlugin()])

        # Verify the hook was registered by checking the registry
        assert agent.hooks.has_callbacks()
