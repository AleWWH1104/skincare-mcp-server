"""Skincare recommendation MCP server (stdio transport)."""

from mcp.server.mcpserver import MCPServer

from models import Product
from services import conflict_engine, inventory_service

mcp = MCPServer(name="skincare")


def _product_to_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "skin_types": product.skin_types,
        "concerns": product.concerns,
        "active_ingredients": product.active_ingredients,
        "price": product.price,
        "stock": product.stock,
        "description": product.description,
    }


@mcp.tool()
def search_products(skin_type: str = "", concern: str = "", in_stock_only: bool = True) -> list[dict]:
    """Search the store's product catalog by skin type and/or skincare concern.

    Args:
        skin_type: e.g. "grasa", "seca", "mixta", "sensible", "normal". Empty to skip this filter.
        concern: e.g. "acné", "manchas", "arrugas", "sensibilidad", "hidratación". Empty to skip this filter.
        in_stock_only: only return products currently in stock.
    """
    results = inventory_service.search_products(
        skin_type=skin_type or None, concern=concern or None, in_stock_only=in_stock_only
    )
    return [_product_to_dict(p) for p in results]


@mcp.tool()
def get_product_details(product_id: str) -> dict:
    """Get full details (price, stock, active ingredients) for one product by its id."""
    product = inventory_service.get_product(product_id)
    if product is None:
        return {"error": f"No product found with id '{product_id}'"}
    return _product_to_dict(product)


@mcp.tool()
def find_alternatives(product_id: str, in_stock_only: bool = True) -> list[dict]:
    """Find other in-stock products sharing at least one active ingredient with
    the given product - useful when it's out of stock or the client wants a
    different brand with the same effect."""
    results = inventory_service.find_alternatives(product_id, in_stock_only=in_stock_only)
    return [_product_to_dict(p) for p in results]


@mcp.tool()
def check_ingredient_conflicts(
    current_ingredients: list[str], candidate_ingredients: list[str]
) -> list[dict]:
    """Check whether a candidate product's active ingredients conflict with
    ingredients the client already uses.

    Args:
        current_ingredients: active ingredients in the client's current routine.
        candidate_ingredients: active ingredients of the product being considered.
    """
    return conflict_engine.find_conflicts(current_ingredients, candidate_ingredients)


@mcp.tool()
def recommend_products(
    skin_type: str, concerns: list[str], current_ingredients: list[str] | None = None
) -> dict:
    """End-to-end recommendation: find in-stock products matching the client's
    skin type and concerns, and flag any that conflict with their current routine.

    Args:
        skin_type: client's skin type, e.g. "grasa".
        concerns: concerns to address, e.g. ["acné", "manchas"].
        current_ingredients: active ingredients already in the client's routine.
    """
    current_ingredients = current_ingredients or []
    candidates: dict[str, Product] = {}
    for concern in concerns:
        for product in inventory_service.search_products(
            skin_type=skin_type, concern=concern, in_stock_only=True
        ):
            candidates[product.id] = product

    recommendations = []
    for product in candidates.values():
        conflicts = conflict_engine.find_conflicts(current_ingredients, product.active_ingredients)
        recommendations.append(
            {
                "product": _product_to_dict(product),
                "conflicts": conflicts,
                "safe_to_combine": len(conflicts) == 0,
            }
        )
    return {"recommendations": recommendations}


if __name__ == "__main__":
    mcp.run()
