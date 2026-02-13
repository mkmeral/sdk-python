"""Tests for SkillsPlugin."""

import unittest.mock
from pathlib import Path

import pytest

from strands.hooks import BeforeInvocationEvent
from strands.plugins.skills_plugin import SkillsPlugin, _SkillsHookProvider
from strands.skills.skill import Skill


def _make_skill_dir(parent: Path, name: str, description: str, allowed_tools: str | None = None) -> Path:
    """Helper to create a skill directory with SKILL.md."""
    skill_path = parent / name
    skill_path.mkdir(exist_ok=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if allowed_tools is not None:
        lines.append(f"allowed-tools: {allowed_tools}")
    lines.extend([
        "---",
        "",
        f"# {name} Instructions",
        "",
        f"Instructions for {name}.",
    ])
    (skill_path / "SKILL.md").write_text("\n".join(lines))
    return skill_path


@pytest.fixture
def skill_dir_a(tmp_path):
    return _make_skill_dir(tmp_path, "skill-a", "Does A things", "tool_x tool_y")


@pytest.fixture
def skill_dir_b(tmp_path):
    return _make_skill_dir(tmp_path, "skill-b", "Does B things")


@pytest.fixture
def skills_parent(tmp_path, skill_dir_a, skill_dir_b):
    return tmp_path


@pytest.fixture
def mock_agent():
    """Create a mock agent with the necessary attributes."""
    agent = unittest.mock.MagicMock()
    agent.system_prompt = "You are a helpful assistant."
    agent.tool_registry.registry = {}
    agent.tool_registry.dynamic_tools = {}

    # Make state.set work like a real dict
    state_data = {}

    def state_set(key, value):
        state_data[key] = value

    def state_get(key=None):
        if key is None:
            return dict(state_data)
        return state_data.get(key)

    agent.state.set.side_effect = state_set
    agent.state.get.side_effect = state_get
    agent._state_data = state_data

    return agent


@pytest.fixture
def mock_agent_with_tools():
    """Create a mock agent with registered tools."""
    agent = unittest.mock.MagicMock()
    agent.system_prompt = "You are a helpful assistant."

    # Create mock tools
    tool_x = unittest.mock.MagicMock()
    tool_x.tool_name = "tool_x"
    tool_x.is_dynamic = False

    tool_y = unittest.mock.MagicMock()
    tool_y.tool_name = "tool_y"
    tool_y.is_dynamic = False

    tool_z = unittest.mock.MagicMock()
    tool_z.tool_name = "tool_z"
    tool_z.is_dynamic = True

    agent.tool_registry.registry = {
        "tool_x": tool_x,
        "tool_y": tool_y,
        "tool_z": tool_z,
    }
    agent.tool_registry.dynamic_tools = {"tool_z": tool_z}

    # Make register_tool actually add to registry
    def register_tool(t):
        agent.tool_registry.registry[t.tool_name] = t

    agent.tool_registry.register_tool.side_effect = register_tool

    # Make state work
    state_data = {}

    def state_set(key, value):
        state_data[key] = value

    def state_get(key=None):
        if key is None:
            return dict(state_data)
        return state_data.get(key)

    agent.state.set.side_effect = state_set
    agent.state.get.side_effect = state_get
    agent._state_data = state_data

    return agent


class TestSkillsPluginInit:
    def test_loads_skills_from_path(self, skill_dir_a):
        plugin = SkillsPlugin(skills=[skill_dir_a])

        assert len(plugin.loaded_skills) == 1
        assert plugin.loaded_skills[0].name == "skill-a"

    def test_loads_skills_from_string_path(self, skill_dir_a):
        plugin = SkillsPlugin(skills=[str(skill_dir_a)])

        assert len(plugin.loaded_skills) == 1

    def test_loads_skill_objects_directly(self):
        skill = Skill(name="direct-skill", description="Directly provided")
        plugin = SkillsPlugin(skills=[skill])

        assert len(plugin.loaded_skills) == 1
        assert plugin.loaded_skills[0].name == "direct-skill"

    def test_loads_skills_from_parent_directory(self, skills_parent):
        plugin = SkillsPlugin(skills=[skills_parent])

        names = sorted(s.name for s in plugin.loaded_skills)
        assert "skill-a" in names
        assert "skill-b" in names

    def test_mixed_sources(self, skill_dir_a):
        skill_obj = Skill(name="obj-skill", description="Object skill")
        plugin = SkillsPlugin(skills=[skill_dir_a, skill_obj])

        assert len(plugin.loaded_skills) == 2
        names = [s.name for s in plugin.loaded_skills]
        assert "skill-a" in names
        assert "obj-skill" in names

    def test_raises_for_nonexistent_path(self, tmp_path):
        with pytest.raises(ValueError, match="Skill path does not exist"):
            SkillsPlugin(skills=[tmp_path / "nonexistent"])

    def test_raises_for_invalid_source(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("not a skill")
        with pytest.raises(ValueError, match="Invalid skill source"):
            SkillsPlugin(skills=[f])

    def test_raises_for_duplicate_skill_names(self, tmp_path):
        skill1 = Skill(name="dup", description="first")
        skill2 = Skill(name="dup", description="second")
        with pytest.raises(ValueError, match="Duplicate skill names found"):
            SkillsPlugin(skills=[skill1, skill2])

    def test_name_property(self, skill_dir_a):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        assert plugin.name == "skills"


class TestSkillsPluginInitPlugin:
    def test_registers_skills_tool(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        mock_agent.tool_registry.register_tool.assert_called_once()
        registered_tool = mock_agent.tool_registry.register_tool.call_args[0][0]
        assert registered_tool.tool_name == "skills"

    def test_registers_hook_provider(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        mock_agent.hooks.add_hook.assert_called_once()
        hook_provider = mock_agent.hooks.add_hook.call_args[0][0]
        assert isinstance(hook_provider, _SkillsHookProvider)

    def test_persists_initial_state(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        mock_agent.state.set.assert_called()
        call_args = mock_agent.state.set.call_args
        assert call_args[0][0] == "skills_plugin"
        state = call_args[0][1]
        assert state["active_skill"] is None
        assert state["filtered_tools"] is None


class TestSkillsPluginActivateDeactivate:
    def test_activate_skill(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        result = plugin.activate_skill("skill-a")

        assert "Instructions for skill-a." in result
        assert plugin.active_skill is not None
        assert plugin.active_skill.name == "skill-a"

    def test_activate_nonexistent_skill_raises(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        with pytest.raises(ValueError, match="Skill 'nonexistent' not found"):
            plugin.activate_skill("nonexistent")

    def test_deactivate_skill(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        plugin.activate_skill("skill-a")
        result = plugin.deactivate_skill()

        assert "deactivated" in result
        assert plugin.active_skill is None

    def test_deactivate_when_none_active(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        result = plugin.deactivate_skill()

        assert "No skill is currently active" in result

    def test_activating_new_skill_deactivates_previous(self, skill_dir_a, skill_dir_b, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a, skill_dir_b])
        plugin.init_plugin(mock_agent)

        plugin.activate_skill("skill-a")
        assert plugin.active_skill.name == "skill-a"

        plugin.activate_skill("skill-b")
        assert plugin.active_skill.name == "skill-b"


class TestToolFiltering:
    def test_filters_tools_on_activate(self, mock_agent_with_tools, tmp_path):
        # skill-a allows only tool_x and tool_y
        skill_dir = _make_skill_dir(tmp_path, "filter-skill", "Filters tools", "tool_x tool_y")
        plugin = SkillsPlugin(skills=[skill_dir])
        plugin.init_plugin(mock_agent_with_tools)

        plugin.activate_skill("filter-skill")

        # tool_z should be removed, tool_x and tool_y and skills should remain
        assert "tool_x" in mock_agent_with_tools.tool_registry.registry
        assert "tool_y" in mock_agent_with_tools.tool_registry.registry
        assert "skills" in mock_agent_with_tools.tool_registry.registry
        assert "tool_z" not in mock_agent_with_tools.tool_registry.registry

    def test_restores_tools_on_deactivate(self, mock_agent_with_tools, tmp_path):
        skill_dir = _make_skill_dir(tmp_path, "filter-skill", "Filters tools", "tool_x")
        plugin = SkillsPlugin(skills=[skill_dir])
        plugin.init_plugin(mock_agent_with_tools)

        plugin.activate_skill("filter-skill")

        # tool_y and tool_z removed
        assert "tool_y" not in mock_agent_with_tools.tool_registry.registry
        assert "tool_z" not in mock_agent_with_tools.tool_registry.registry

        plugin.deactivate_skill()

        # All tools restored
        assert "tool_y" in mock_agent_with_tools.tool_registry.registry
        assert "tool_z" in mock_agent_with_tools.tool_registry.registry

    def test_restores_tools_when_switching_skills(self, mock_agent_with_tools, tmp_path):
        skill_dir_1 = _make_skill_dir(tmp_path, "skill-1", "First skill", "tool_x")
        skill_dir_2 = _make_skill_dir(tmp_path, "skill-2", "Second skill", "tool_z")
        plugin = SkillsPlugin(skills=[skill_dir_1, skill_dir_2])
        plugin.init_plugin(mock_agent_with_tools)

        plugin.activate_skill("skill-1")
        assert "tool_z" not in mock_agent_with_tools.tool_registry.registry

        plugin.activate_skill("skill-2")
        # Tools should be restored then re-filtered for skill-2
        assert "tool_z" in mock_agent_with_tools.tool_registry.registry
        assert "tool_x" not in mock_agent_with_tools.tool_registry.registry

    def test_no_filtering_when_allowed_tools_none(self, mock_agent_with_tools, tmp_path):
        skill_dir = _make_skill_dir(tmp_path, "no-filter", "No filtering")
        plugin = SkillsPlugin(skills=[skill_dir])
        plugin.init_plugin(mock_agent_with_tools)

        original_tools = set(mock_agent_with_tools.tool_registry.registry.keys())

        plugin.activate_skill("no-filter")

        # Only the skills tool should be added, no tools removed
        current_tools = set(mock_agent_with_tools.tool_registry.registry.keys())
        assert original_tools.issubset(current_tools)

    def test_warns_for_nonexistent_allowed_tool(self, mock_agent_with_tools, tmp_path, caplog):
        skill_dir = _make_skill_dir(tmp_path, "bad-tools", "Has nonexistent tool", "tool_x nonexistent_tool")
        plugin = SkillsPlugin(skills=[skill_dir])
        plugin.init_plugin(mock_agent_with_tools)

        import logging

        with caplog.at_level(logging.WARNING):
            plugin.activate_skill("bad-tools")

        assert "allowed tool not found in agent" in caplog.text


class TestSystemPromptInjection:
    def test_generates_skill_summary(self, skill_dir_a, skill_dir_b):
        plugin = SkillsPlugin(skills=[skill_dir_a, skill_dir_b])

        addition = plugin.get_system_prompt_addition()

        assert "## Available Skills" in addition
        assert "**skill-a**" in addition
        assert "**skill-b**" in addition

    def test_includes_active_skill_instructions(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)
        plugin.activate_skill("skill-a")

        addition = plugin.get_system_prompt_addition()

        assert "## Active Skill: skill-a" in addition
        assert "Instructions for skill-a." in addition

    def test_no_active_skill_section_when_none_active(self, skill_dir_a):
        plugin = SkillsPlugin(skills=[skill_dir_a])

        addition = plugin.get_system_prompt_addition()

        assert "## Active Skill" not in addition

    def test_empty_addition_when_no_skills(self):
        plugin = SkillsPlugin.__new__(SkillsPlugin)
        plugin._loaded_skills = []
        plugin._active_skill = None

        assert plugin.get_system_prompt_addition() == ""

    def test_hook_injects_into_system_prompt(self, skill_dir_a, skill_dir_b):
        plugin = SkillsPlugin(skills=[skill_dir_a, skill_dir_b])
        plugin._original_system_prompt = None

        # Create a mock agent for the event
        agent = unittest.mock.MagicMock()
        agent.system_prompt = "Base prompt."

        hook_provider = _SkillsHookProvider(plugin)
        event = unittest.mock.MagicMock(spec=BeforeInvocationEvent)
        event.agent = agent

        hook_provider._inject_system_prompt(event)

        new_prompt = agent.system_prompt
        assert "Base prompt." in new_prompt
        assert "## Available Skills" in new_prompt

    def test_hook_does_not_accumulate_prompts(self, skill_dir_a):
        """Verify that repeated invocations don't keep appending to the prompt."""
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin._original_system_prompt = None

        agent = unittest.mock.MagicMock()
        agent.system_prompt = "Base prompt."

        hook_provider = _SkillsHookProvider(plugin)
        event = unittest.mock.MagicMock(spec=BeforeInvocationEvent)
        event.agent = agent

        # Inject twice
        hook_provider._inject_system_prompt(event)
        first_prompt = agent.system_prompt

        hook_provider._inject_system_prompt(event)
        second_prompt = agent.system_prompt

        assert first_prompt == second_prompt


class TestSessionPersistence:
    def test_state_persisted_on_init(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        state = mock_agent._state_data.get("skills_plugin")
        assert state is not None
        assert state["active_skill"] is None
        assert state["filtered_tools"] is None

    def test_state_updated_on_activate(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        plugin.activate_skill("skill-a")

        state = mock_agent._state_data.get("skills_plugin")
        assert state["active_skill"] == "skill-a"

    def test_state_updated_on_deactivate(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        plugin.activate_skill("skill-a")
        plugin.deactivate_skill()

        state = mock_agent._state_data.get("skills_plugin")
        assert state["active_skill"] is None

    def test_state_includes_skill_paths(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        state = mock_agent._state_data.get("skills_plugin")
        assert len(state["skills"]) == 1
        assert str(skill_dir_a.resolve()) in state["skills"][0]


class TestSkillsTool:
    def test_skills_tool_spec(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        registered_tool = mock_agent.tool_registry.register_tool.call_args[0][0]
        spec = registered_tool.tool_spec

        assert spec["name"] == "skills"
        assert "action" in spec["inputSchema"]["json"]["properties"]
        assert "skill_name" in spec["inputSchema"]["json"]["properties"]

    def test_skills_tool_activate_action(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        registered_tool = mock_agent.tool_registry.register_tool.call_args[0][0]
        # Call the underlying function directly
        result = registered_tool("activate", "skill-a")

        assert "Instructions for skill-a." in result

    def test_skills_tool_deactivate_action(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        registered_tool = mock_agent.tool_registry.register_tool.call_args[0][0]
        registered_tool("activate", "skill-a")
        result = registered_tool("deactivate", "skill-a")

        assert "deactivated" in result

    def test_skills_tool_unknown_action(self, skill_dir_a, mock_agent):
        plugin = SkillsPlugin(skills=[skill_dir_a])
        plugin.init_plugin(mock_agent)

        registered_tool = mock_agent.tool_registry.register_tool.call_args[0][0]
        result = registered_tool("invalid", "skill-a")

        assert "Unknown action" in result
