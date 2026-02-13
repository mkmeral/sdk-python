"""Tests for Skill dataclass and loading utilities."""

import pytest

from strands.skills.skill import Skill, _parse_simple_yaml, _parse_skill_md, load_skill, load_skills


@pytest.fixture
def skill_dir(tmp_path):
    """Create a valid skill directory with SKILL.md."""
    skill_path = tmp_path / "code-review"
    skill_path.mkdir()
    skill_md = skill_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: code-review\n"
        "description: Reviews code for bugs and security\n"
        "allowed-tools: file_read shell\n"
        "---\n"
        "\n"
        "# Code Review Instructions\n"
        "\n"
        "Review all code for bugs.\n"
    )
    return skill_path


@pytest.fixture
def skill_dir_no_allowed_tools(tmp_path):
    """Create a skill directory without allowed-tools."""
    skill_path = tmp_path / "docs"
    skill_path.mkdir()
    skill_md = skill_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: documentation\n"
        "description: Generates documentation\n"
        "---\n"
        "\n"
        "# Documentation Instructions\n"
        "\n"
        "Generate clear documentation.\n"
    )
    return skill_path


@pytest.fixture
def skills_parent_dir(tmp_path, skill_dir, skill_dir_no_allowed_tools):
    """Create a parent directory with multiple skill subdirectories."""
    # skill_dir and skill_dir_no_allowed_tools are already children of tmp_path
    return tmp_path


class TestSkillFromPath:
    def test_loads_valid_skill(self, skill_dir):
        skill = Skill.from_path(skill_dir)

        assert skill.name == "code-review"
        assert skill.description == "Reviews code for bugs and security"
        assert skill.allowed_tools == ["file_read", "shell"]
        assert "Code Review Instructions" in skill.instructions
        assert "Review all code for bugs." in skill.instructions
        assert skill.path == skill_dir.resolve()

    def test_loads_skill_without_allowed_tools(self, skill_dir_no_allowed_tools):
        skill = Skill.from_path(skill_dir_no_allowed_tools)

        assert skill.name == "documentation"
        assert skill.description == "Generates documentation"
        assert skill.allowed_tools is None
        assert "Documentation Instructions" in skill.instructions

    def test_raises_for_nonexistent_path(self, tmp_path):
        with pytest.raises(ValueError, match="Skill path does not exist"):
            Skill.from_path(tmp_path / "nonexistent")

    def test_raises_for_file_path(self, tmp_path):
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        with pytest.raises(ValueError, match="Skill path is not a directory"):
            Skill.from_path(file_path)

    def test_raises_for_missing_skill_md(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(ValueError, match="No SKILL.md found"):
            Skill.from_path(empty_dir)

    def test_raises_for_missing_name_field(self, tmp_path):
        skill_path = tmp_path / "bad-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "description: No name field\n"
            "---\n"
            "\n"
            "Instructions.\n"
        )
        with pytest.raises(ValueError, match="Missing required 'name' field"):
            Skill.from_path(skill_path)

    def test_raises_for_malformed_frontmatter_no_start(self, tmp_path):
        skill_path = tmp_path / "bad-frontmatter"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("No frontmatter here\n")
        with pytest.raises(ValueError, match="must start with YAML frontmatter"):
            Skill.from_path(skill_path)

    def test_raises_for_malformed_frontmatter_no_end(self, tmp_path):
        skill_path = tmp_path / "bad-frontmatter2"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("---\nname: test\n")
        with pytest.raises(ValueError, match="missing closing '---' delimiter"):
            Skill.from_path(skill_path)

    def test_extra_frontmatter_goes_to_metadata(self, tmp_path):
        skill_path = tmp_path / "extra-meta"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: extra-skill\n"
            "description: has extra metadata\n"
            "version: 1.0\n"
            "author: test-author\n"
            "---\n"
            "\n"
            "Instructions.\n"
        )
        skill = Skill.from_path(skill_path)

        assert skill.metadata == {"version": "1.0", "author": "test-author"}

    def test_allowed_tools_as_list_in_yaml(self, tmp_path):
        """Test that allowed-tools can be a space-separated string."""
        skill_path = tmp_path / "list-tools"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: list-tools\n"
            "description: test\n"
            "allowed-tools: tool_a tool_b tool_c\n"
            "---\n"
            "\n"
            "Instructions.\n"
        )
        skill = Skill.from_path(skill_path)

        assert skill.allowed_tools == ["tool_a", "tool_b", "tool_c"]

    def test_empty_description_defaults_to_empty_string(self, tmp_path):
        skill_path = tmp_path / "no-desc"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: no-desc\n"
            "---\n"
            "\n"
            "Instructions.\n"
        )
        skill = Skill.from_path(skill_path)

        assert skill.description == ""


class TestLoadSkill:
    def test_load_skill(self, skill_dir):
        skill = load_skill(skill_dir)

        assert skill.name == "code-review"

    def test_load_skill_string_path(self, skill_dir):
        skill = load_skill(str(skill_dir))

        assert skill.name == "code-review"


class TestLoadSkills:
    def test_loads_all_skills_from_parent(self, skills_parent_dir):
        skills = load_skills(skills_parent_dir)

        names = sorted(s.name for s in skills)
        assert "code-review" in names
        assert "documentation" in names

    def test_skips_dirs_without_skill_md(self, tmp_path):
        empty_dir = tmp_path / "not-a-skill"
        empty_dir.mkdir()
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: real\ndescription: real\n---\n\nInstructions.\n"
        )

        skills = load_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "real"

    def test_raises_for_nonexistent_dir(self, tmp_path):
        with pytest.raises(ValueError, match="Skills directory does not exist"):
            load_skills(tmp_path / "nonexistent")

    def test_raises_for_file_not_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Skills directory is not a directory"):
            load_skills(f)

    def test_returns_empty_for_dir_with_no_skills(self, tmp_path):
        (tmp_path / "empty-subdir").mkdir()
        skills = load_skills(tmp_path)
        assert skills == []


class TestParseSimpleYaml:
    def test_basic_key_value(self):
        result = _parse_simple_yaml("name: test\ndescription: hello")
        assert result == {"name": "test", "description": "hello"}

    def test_quoted_values(self):
        result = _parse_simple_yaml('name: "test value"\ndescription: \'hello world\'')
        assert result == {"name": "test value", "description": "hello world"}

    def test_ignores_comments(self):
        result = _parse_simple_yaml("# comment\nname: test")
        assert result == {"name": "test"}

    def test_ignores_empty_lines(self):
        result = _parse_simple_yaml("\nname: test\n\ndescription: hello\n")
        assert result == {"name": "test", "description": "hello"}

    def test_handles_colons_in_values(self):
        result = _parse_simple_yaml("name: test: value")
        assert result == {"name": "test: value"}


class TestParseSkillMd:
    def test_basic_parse(self):
        content = "---\nname: test\n---\n\nInstructions here."
        frontmatter, instructions = _parse_skill_md(content)
        assert frontmatter == {"name": "test"}
        assert "Instructions here." in instructions

    def test_empty_instructions(self):
        content = "---\nname: test\n---\n"
        frontmatter, instructions = _parse_skill_md(content)
        assert frontmatter == {"name": "test"}
        assert instructions.strip() == ""


class TestSkillDataclass:
    def test_default_values(self):
        skill = Skill(name="test", description="desc")
        assert skill.instructions == ""
        assert skill.path is None
        assert skill.allowed_tools is None
        assert skill.metadata == {}

    def test_with_all_fields(self, tmp_path):
        skill = Skill(
            name="test",
            description="desc",
            instructions="Do things",
            path=tmp_path,
            allowed_tools=["tool_a"],
            metadata={"version": "1.0"},
        )
        assert skill.name == "test"
        assert skill.allowed_tools == ["tool_a"]
        assert skill.metadata == {"version": "1.0"}
