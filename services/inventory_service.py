"""Queries against the simulated store inventory."""

import json
from pathlib import Path

from models import Product

INVENTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "inventory.json"


def load_products() -> list[Product]:
    with INVENTORY_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return [Product(**p) for p in raw]


def search_products(
    skin_type: str | None = None, concern: str | None = None, in_stock_only: bool = True
) -> list[Product]:
    results = []
    for product in load_products():
        if skin_type and skin_type.lower() not in [s.lower() for s in product.skin_types]:
            continue
        if concern and concern.lower() not in [c.lower() for c in product.concerns]:
            continue
        if in_stock_only and product.stock <= 0:
            continue
        results.append(product)
    return results


def get_product(product_id: str) -> Product | None:
    for product in load_products():
        if product.id == product_id:
            return product
    return None


def find_alternatives(product_id: str, in_stock_only: bool = True) -> list[Product]:
    """Other products sharing at least one active ingredient with product_id."""
    target = get_product(product_id)
    if target is None:
        return []

    target_ingredients = {i.lower() for i in target.active_ingredients}
    alternatives = []
    for product in load_products():
        if product.id == target.id:
            continue
        if in_stock_only and product.stock <= 0:
            continue
        shared = target_ingredients & {i.lower() for i in product.active_ingredients}
        if shared:
            alternatives.append(product)
    return alternatives
