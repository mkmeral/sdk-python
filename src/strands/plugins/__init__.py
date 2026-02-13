"""Plugin system for extending Strands Agents.

Plugins provide a composable way to extend agent functionality by bundling tools, hooks, and configuration into a
single reusable package.
"""

from .plugin import Plugin
from .skills_plugin import SkillsPlugin

__all__ = [
    "Plugin",
    "SkillsPlugin",
]
