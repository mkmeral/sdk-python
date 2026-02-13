"""Tests for Plugin protocol."""

import unittest.mock

from strands.plugins.plugin import Plugin


class TestPluginProtocol:
    def test_class_satisfies_protocol(self):
        """Test that a class with the right interface satisfies the Plugin protocol."""

        class MyPlugin:
            @property
            def name(self) -> str:
                return "my-plugin"

            def init_plugin(self, agent) -> None:
                pass

        assert isinstance(MyPlugin(), Plugin)

    def test_class_without_name_does_not_satisfy(self):
        """Test that a class without name does not satisfy the Plugin protocol."""

        class NotAPlugin:
            def init_plugin(self, agent) -> None:
                pass

        assert not isinstance(NotAPlugin(), Plugin)

    def test_class_without_init_plugin_does_not_satisfy(self):
        """Test that a class without init_plugin does not satisfy the Plugin protocol."""

        class NotAPlugin:
            @property
            def name(self) -> str:
                return "not-a-plugin"

        assert not isinstance(NotAPlugin(), Plugin)
