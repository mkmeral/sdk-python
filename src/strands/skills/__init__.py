"""Skills module for Strands Agents.

Skills are reusable instruction packages following the AgentSkills.io spec.
"""

from .skill import Skill, load_skill, load_skills

__all__ = [
    "Skill",
    "load_skill",
    "load_skills",
]
