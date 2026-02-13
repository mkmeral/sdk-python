"""SkillsPlugin for Strands Agents.

This plugin provides skill-based instruction management. Skills are reusable instruction packages
that can be activated/deactivated at runtime, with optional tool filtering.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

from ..hooks import BeforeInvocationEvent, HookProvider, HookRegistry
from ..skills.skill import Skill, load_skills
from ..tools.decorator import DecoratedFunctionTool, tool
from ..types.tools import AgentTool

if TYPE_CHECKING:
    from ..agent.agent import Agent

logger = logging.getLogger(__name__)


class SkillsPlugin:
    """Plugin that provides skill-based instruction management for agents.

    Skills are reusable instruction packages following the AgentSkills.io spec. The plugin:

    1. Loads skills from filesystem paths or ``Skill`` objects
    2. Registers a ``skills`` tool for activating/deactivating skills at runtime
    3. Injects skill metadata into the system prompt before each invocation
    4. Optionally filters available tools when a skill with ``allowed_tools`` is active

    Example::

        from strands import Agent
        from strands.plugins import SkillsPlugin

        agent = Agent(
            plugins=[SkillsPlugin(skills=["./skills/code-review", "./skills/documentation"])]
        )

    Attributes:
        name: The plugin name, always ``"skills"``.
    """

    name: str = "skills"

    def __init__(self, skills: list[Union[str, Path, Skill]]) -> None:
        """Initialize the SkillsPlugin.

        Args:
            skills: List of skill sources. Each item can be:
                - A ``Skill`` object
                - A path to a directory containing SKILL.md (single skill)
                - A path to a parent directory containing skill subdirectories

        Raises:
            ValueError: If any skill path is invalid or contains malformed SKILL.md.
        """
        self._loaded_skills: list[Skill] = []
        self._active_skill: Union[Skill, None] = None
        self._filtered_tools: Union[list[str], None] = None
        self._removed_tools: dict[str, AgentTool] = {}
        self._agent: Union["Agent", None] = None
        self._original_system_prompt: Union[str, None] = None

        for source in skills:
            if isinstance(source, Skill):
                self._loaded_skills.append(source)
            else:
                path = Path(source).resolve()
                if not path.exists():
                    raise ValueError(f"Skill path does not exist: {path}")

                skill_file = path / "SKILL.md"
                if skill_file.exists():
                    # Single skill directory
                    self._loaded_skills.append(Skill.from_path(path))
                elif path.is_dir():
                    # Parent directory containing skill subdirectories
                    loaded = load_skills(path)
                    if not loaded:
                        logger.warning("skills_dir=<%s> | no skills found in directory", path)
                    self._loaded_skills.extend(loaded)
                else:
                    raise ValueError(f"Invalid skill source: {path} (not a directory or does not contain SKILL.md)")

        if not self._loaded_skills:
            logger.warning("SkillsPlugin initialized with no skills")

        # Validate no duplicate skill names
        names = [s.name for s in self._loaded_skills]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            raise ValueError(f"Duplicate skill names found: {set(duplicates)}")

    def init_plugin(self, agent: "Agent") -> None:
        """Initialize the plugin with the given agent.

        Registers the skills tool and the system prompt injection hook.

        Args:
            agent: The agent instance to extend.
        """
        self._agent = agent

        # Register the skills tool
        skills_tool = self._create_skills_tool()
        agent.tool_registry.register_tool(skills_tool)

        # Register the hook provider for system prompt injection
        agent.hooks.add_hook(_SkillsHookProvider(self))

        # Initialize state
        self._persist_state()

    @property
    def loaded_skills(self) -> list[Skill]:
        """Get the list of loaded skills."""
        return list(self._loaded_skills)

    @property
    def active_skill(self) -> Union[Skill, None]:
        """Get the currently active skill, or None."""
        return self._active_skill

    def activate_skill(self, skill_name: str) -> str:
        """Activate a skill by name.

        Only one skill can be active at a time. Activating a new skill implicitly deactivates the
        previous one.

        Args:
            skill_name: Name of the skill to activate.

        Returns:
            The skill's instructions text.

        Raises:
            ValueError: If no skill with the given name is found.
        """
        skill = self._find_skill(skill_name)
        if skill is None:
            available = [s.name for s in self._loaded_skills]
            raise ValueError(f"Skill '{skill_name}' not found. Available skills: {available}")

        # Deactivate current skill if one is active (restore tools first)
        if self._active_skill is not None:
            self._restore_tools()

        self._active_skill = skill

        # Apply tool filtering if the skill specifies allowed_tools
        if skill.allowed_tools is not None and self._agent is not None:
            self._apply_tool_filter(skill.allowed_tools)

        self._persist_state()

        return skill.instructions

    def deactivate_skill(self) -> str:
        """Deactivate the currently active skill.

        Returns:
            A confirmation message.
        """
        if self._active_skill is None:
            return "No skill is currently active."

        skill_name = self._active_skill.name
        self._restore_tools()
        self._active_skill = None
        self._persist_state()

        return f"Skill '{skill_name}' has been deactivated."

    def get_system_prompt_addition(self) -> str:
        """Generate the system prompt addition for skills.

        Returns:
            A string to append to the system prompt containing skill metadata.
        """
        if not self._loaded_skills:
            return ""

        lines = [
            "\n\n## Available Skills\n",
            "You have access to specialized skills. When a task matches a skill's description, "
            "use the skills tool to activate it and read its full instructions.\n",
        ]

        for skill in self._loaded_skills:
            lines.append(f"- **{skill.name}**: {skill.description}")

        if self._active_skill is not None:
            lines.append(f"\n\n## Active Skill: {self._active_skill.name}\n")
            lines.append(self._active_skill.instructions)

        return "\n".join(lines)

    def _find_skill(self, skill_name: str) -> Union[Skill, None]:
        """Find a skill by name."""
        for skill in self._loaded_skills:
            if skill.name == skill_name:
                return skill
        return None

    def _apply_tool_filter(self, allowed_tools: list[str]) -> None:
        """Filter agent tools to only those allowed by the active skill.

        The skills tool itself is always kept available. Removed tools are stored
        internally so they can be restored when the skill is deactivated.

        Args:
            allowed_tools: List of tool names to keep.
        """
        if self._agent is None:
            return

        current_tools = list(self._agent.tool_registry.registry.keys())
        # Always keep the skills tool available
        always_keep = {"skills"}
        tools_to_remove = [t for t in current_tools if t not in allowed_tools and t not in always_keep]

        # Warn about allowed_tools that don't exist
        existing_tools = set(current_tools)
        for tool_name in allowed_tools:
            if tool_name not in existing_tools:
                logger.warning(
                    "skill=<%s>, tool=<%s> | allowed tool not found in agent",
                    self._active_skill.name if self._active_skill else "unknown",
                    tool_name,
                )

        if tools_to_remove:
            self._filtered_tools = tools_to_remove
            # Store removed tools for later restoration
            for tool_name in tools_to_remove:
                if tool_name in self._agent.tool_registry.registry:
                    self._removed_tools[tool_name] = self._agent.tool_registry.registry.pop(tool_name)
                if tool_name in self._agent.tool_registry.dynamic_tools:
                    del self._agent.tool_registry.dynamic_tools[tool_name]

    def _restore_tools(self) -> None:
        """Restore previously filtered tools to the agent's registry."""
        if self._agent is None or not self._removed_tools:
            return

        for tool_name, tool_obj in self._removed_tools.items():
            self._agent.tool_registry.registry[tool_name] = tool_obj
            if tool_obj.is_dynamic:
                self._agent.tool_registry.dynamic_tools[tool_name] = tool_obj

        self._removed_tools.clear()
        self._filtered_tools = None

    def _persist_state(self) -> None:
        """Persist plugin state to agent.state."""
        if self._agent is None:
            return

        self._agent.state.set(
            "skills_plugin",
            {
                "skills": [str(s.path) for s in self._loaded_skills if s.path],
                "active_skill": self._active_skill.name if self._active_skill else None,
                "filtered_tools": self._filtered_tools if self._filtered_tools else None,
            },
        )

    def _create_skills_tool(self) -> DecoratedFunctionTool:
        """Create the skills tool for runtime skill management.

        Returns:
            A DecoratedFunctionTool wrapping the skills action handler.
        """
        plugin = self

        @tool
        def skills(action: str, skill_name: str) -> str:
            """Activate or deactivate a skill.

            Use this tool to activate a skill when a task matches its description. Only one skill can be
            active at a time. Activating a new skill implicitly deactivates the previous one.

            Args:
                action: The action to perform. Must be "activate" or "deactivate".
                skill_name: The name of the skill to activate or deactivate.

            Returns:
                The skill instructions on activate, or a confirmation message on deactivate.
            """
            if action == "activate":
                return plugin.activate_skill(skill_name)
            elif action == "deactivate":
                return plugin.deactivate_skill()
            else:
                return f"Unknown action '{action}'. Use 'activate' or 'deactivate'."

        return skills


class _SkillsHookProvider(HookProvider):
    """Hook provider that injects skill metadata into the system prompt."""

    def __init__(self, plugin: SkillsPlugin) -> None:
        self._plugin = plugin

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before-invocation hook for system prompt injection.

        Args:
            registry: The hook registry to register with.
            **kwargs: Additional keyword arguments.
        """
        registry.add_callback(BeforeInvocationEvent, self._inject_system_prompt)

    def _inject_system_prompt(self, event: BeforeInvocationEvent) -> None:
        """Inject skill information into the system prompt before each invocation.

        Args:
            event: The before-invocation event.
        """
        agent = event.agent
        addition = self._plugin.get_system_prompt_addition()
        if not addition:
            return

        current_prompt = agent.system_prompt or ""

        # Store the original system prompt on first injection so we don't keep appending
        if self._plugin._original_system_prompt is None:
            self._plugin._original_system_prompt = current_prompt

        # Always rebuild from the original to avoid accumulation
        agent.system_prompt = self._plugin._original_system_prompt + addition
