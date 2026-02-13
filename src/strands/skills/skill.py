"""Skill dataclass and loading utilities.

Skills are reusable instruction packages following the AgentSkills.io spec. A skill is a folder with a SKILL.md file
containing YAML frontmatter (name, description, allowed-tools) and markdown instructions.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger(__name__)

_SKILL_FILENAME = "SKILL.md"


@dataclass
class Skill:
    """A reusable instruction package for an agent.

    Attributes:
        name: The unique name of the skill.
        description: A human-readable description of what the skill does.
        instructions: The full markdown instructions for the skill.
        path: The filesystem path where this skill was loaded from, if applicable.
        allowed_tools: List of tool names allowed when this skill is active.
            None means all tools are allowed.
        metadata: Additional metadata from the SKILL.md frontmatter.
    """

    name: str
    description: str
    instructions: str = ""
    path: Union[Path, None] = None
    allowed_tools: Union[list[str], None] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_path(cls, skill_path: Union[str, Path]) -> "Skill":
        """Load a skill from a directory containing a SKILL.md file.

        Args:
            skill_path: Path to the directory containing SKILL.md.

        Returns:
            A Skill instance populated from the SKILL.md file.

        Raises:
            ValueError: If the path doesn't exist, is not a directory, or
                doesn't contain a valid SKILL.md file.
        """
        path = Path(skill_path).resolve()

        if not path.exists():
            raise ValueError(f"Skill path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Skill path is not a directory: {path}")

        skill_file = path / _SKILL_FILENAME
        if not skill_file.exists():
            raise ValueError(f"No {_SKILL_FILENAME} found in: {path}")

        content = skill_file.read_text(encoding="utf-8")
        frontmatter, instructions = _parse_skill_md(content)

        name = frontmatter.get("name")
        if not name:
            raise ValueError(f"Missing required 'name' field in {_SKILL_FILENAME} frontmatter: {skill_file}")

        description = frontmatter.get("description", "")

        allowed_tools = None
        raw_allowed_tools = frontmatter.get("allowed-tools")
        if raw_allowed_tools is not None:
            if isinstance(raw_allowed_tools, str):
                allowed_tools = raw_allowed_tools.split()
            elif isinstance(raw_allowed_tools, list):
                allowed_tools = [str(t) for t in raw_allowed_tools]

        # Collect any extra frontmatter fields as metadata
        reserved_keys = {"name", "description", "allowed-tools"}
        metadata = {k: v for k, v in frontmatter.items() if k not in reserved_keys}

        return cls(
            name=name,
            description=description,
            instructions=instructions.strip(),
            path=path,
            allowed_tools=allowed_tools,
            metadata=metadata,
        )


def load_skill(skill_path: Union[str, Path]) -> Skill:
    """Load a single skill from a directory.

    This is a convenience wrapper around ``Skill.from_path``.

    Args:
        skill_path: Path to the directory containing SKILL.md.

    Returns:
        A Skill instance.

    Raises:
        ValueError: If the path is invalid or SKILL.md is malformed.
    """
    return Skill.from_path(skill_path)


def load_skills(skills_dir: Union[str, Path]) -> list[Skill]:
    """Load all skills from subdirectories of a parent directory.

    Each immediate subdirectory of ``skills_dir`` that contains a SKILL.md file will be loaded as a skill.
    Subdirectories without SKILL.md are silently skipped.

    Args:
        skills_dir: Parent directory containing skill subdirectories.

    Returns:
        List of loaded Skill instances.

    Raises:
        ValueError: If skills_dir doesn't exist or is not a directory.
    """
    path = Path(skills_dir).resolve()

    if not path.exists():
        raise ValueError(f"Skills directory does not exist: {path}")

    if not path.is_dir():
        raise ValueError(f"Skills directory is not a directory: {path}")

    skills: list[Skill] = []
    for child in sorted(path.iterdir()):
        if child.is_dir() and (child / _SKILL_FILENAME).exists():
            try:
                skills.append(Skill.from_path(child))
            except ValueError:
                logger.warning("skill_path=<%s> | failed to load skill, skipping", child)

    return skills


def _parse_skill_md(content: str) -> tuple[dict[str, Any], str]:
    """Parse a SKILL.md file into frontmatter dict and instructions body.

    The frontmatter is delimited by ``---`` markers at the start of the file.
    Uses a simple YAML-subset parser to avoid requiring PyYAML as a dependency.

    Args:
        content: The full text content of a SKILL.md file.

    Returns:
        A tuple of (frontmatter_dict, instructions_body).

    Raises:
        ValueError: If the frontmatter is malformed.
    """
    content = content.strip()

    # Check for frontmatter delimiters
    if not content.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")

    # Find the closing ---
    second_marker = content.find("---", 3)
    if second_marker == -1:
        raise ValueError("SKILL.md frontmatter is missing closing '---' delimiter")

    frontmatter_text = content[3:second_marker].strip()
    instructions = content[second_marker + 3:]

    frontmatter = _parse_simple_yaml(frontmatter_text)

    return frontmatter, instructions


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse a simple YAML-like key-value format.

    Supports only flat key: value pairs. This avoids requiring PyYAML as a dependency.

    Args:
        text: The YAML-like text to parse.

    Returns:
        A dictionary of parsed key-value pairs.
    """
    result: dict[str, Any] = {}

    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()

            # Remove surrounding quotes if present
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            result[key] = value

    return result
