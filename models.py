"""Data shapes for the product catalog and the ingredient rule set."""

from dataclasses import dataclass


@dataclass
class Product:
    id: str
    name: str
    brand: str
    category: str
    skin_types: list[str]
    concerns: list[str]
    active_ingredients: list[str]
    price: float
    stock: int
    description: str = ""


@dataclass
class ConflictRule:
    ingredient_a: str
    ingredient_b: str
    severity: str  # "avoid" | "caution"
    reason: str
    recommendation: str
