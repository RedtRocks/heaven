"""Loads the Check-in Question bank used for the Seed Interview."""

import json
from dataclasses import dataclass
from pathlib import Path

QUESTIONS_PATH = Path(__file__).parent / "seed_questions.json"


@dataclass(frozen=True)
class SeedQuestion:
    id: str
    text: str
    category: str
    per_relationship: bool = False


def load_seed_questions() -> list[SeedQuestion]:
    data = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [SeedQuestion(**q) for q in data]
