"""Checks ingredient pairs against a rule set of known skincare interactions."""

import json
from pathlib import Path

from models import ConflictRule

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_rules.json"


def load_rules() -> list[ConflictRule]:
    with RULES_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return [ConflictRule(**r) for r in raw]


def find_conflicts(current_ingredients: list[str], candidate_ingredients: list[str]) -> list[dict]:
    """Check every current-vs-candidate ingredient pair, and pairs within the
    candidate itself, against the rule set."""
    current_set = {i.lower() for i in current_ingredients}
    candidate_set = {i.lower() for i in candidate_ingredients}

    conflicts = []
    for rule in load_rules():
        a, b = rule.ingredient_a.lower(), rule.ingredient_b.lower()
        crosses_routines = (a in current_set and b in candidate_set) or (
            b in current_set and a in candidate_set
        )
        within_candidate = a in candidate_set and b in candidate_set
        if crosses_routines or within_candidate:
            conflicts.append(
                {
                    "ingredients": [rule.ingredient_a, rule.ingredient_b],
                    "severity": rule.severity,
                    "reason": rule.reason,
                    "recommendation": rule.recommendation,
                }
            )
    return conflicts
