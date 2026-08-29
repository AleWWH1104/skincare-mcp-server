"""Skincare recommendation MCP server (stdio transport).

Reads newline-delimited JSON-RPC 2.0 requests from stdin and writes
responses to stdout, per the MCP transport spec.
"""

import json
import sys
from typing import Any, Callable

from models import Product
from services import conflict_engine, inventory_service

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "skincare", "version": "0.1.0"}


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


def search_products(skin_type: str = "", concern: str = "", in_stock_only: bool = True) -> list[dict]:
    """Search the store's product catalog by skin type and/or skincare concern."""
    results = inventory_service.search_products(
        skin_type=skin_type or None, concern=concern or None, in_stock_only=in_stock_only
    )
    return [_product_to_dict(p) for p in results]


def get_product_details(product_id: str) -> dict:
    """Get full details (price, stock, active ingredients) for one product by its id."""
    product = inventory_service.get_product(product_id)
    if product is None:
        return {"error": f"No product found with id '{product_id}'"}
    return _product_to_dict(product)


def find_alternatives(product_id: str, in_stock_only: bool = True) -> list[dict]:
    """Find other in-stock products sharing at least one active ingredient with
    the given product - useful when it's out of stock or the client wants a
    different brand with the same effect."""
    results = inventory_service.find_alternatives(product_id, in_stock_only=in_stock_only)
    return [_product_to_dict(p) for p in results]


def check_ingredient_conflicts(
    current_ingredients: list[str], candidate_ingredients: list[str]
) -> list[dict]:
    """Check whether a candidate product's active ingredients conflict with
    ingredients the client already uses."""
    return conflict_engine.find_conflicts(current_ingredients, candidate_ingredients)


def recommend_products(
    skin_type: str, concerns: list[str], current_ingredients: list[str] | None = None
) -> dict:
    """End-to-end recommendation: find in-stock products matching the client's
    skin type and concerns, and flag any that conflict with their current routine."""
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


TOOLS: dict[str, Callable[..., Any]] = {
    "search_products": search_products,
    "get_product_details": get_product_details,
    "find_alternatives": find_alternatives,
    "check_ingredient_conflicts": check_ingredient_conflicts,
    "recommend_products": recommend_products,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search the store's product catalog by skin type and/or skincare concern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skin_type": {
                    "type": "string",
                    "description": 'e.g. "grasa", "seca", "mixta", "sensible", "normal". Empty to skip this filter.',
                    "default": "",
                },
                "concern": {
                    "type": "string",
                    "description": 'e.g. "acné", "manchas", "arrugas", "sensibilidad", "hidratación". Empty to skip this filter.',
                    "default": "",
                },
                "in_stock_only": {
                    "type": "boolean",
                    "description": "Only return products currently in stock.",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "get_product_details",
        "description": "Get full details (price, stock, active ingredients) for one product by its id.",
        "inputSchema": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "find_alternatives",
        "description": (
            "Find other in-stock products sharing at least one active ingredient with "
            "the given product - useful when it's out of stock or the client wants a "
            "different brand with the same effect."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "in_stock_only": {"type": "boolean", "default": True},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "check_ingredient_conflicts",
        "description": (
            "Check whether a candidate product's active ingredients conflict with "
            "ingredients the client already uses."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "current_ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Active ingredients in the client's current routine.",
                },
                "candidate_ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Active ingredients of the product being considered.",
                },
            },
            "required": ["current_ingredients", "candidate_ingredients"],
        },
    },
    {
        "name": "recommend_products",
        "description": (
            "End-to-end recommendation: find in-stock products matching the client's "
            "skin type and concerns, and flag any that conflict with their current routine."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "skin_type": {"type": "string", "description": 'e.g. "grasa".'},
                "concerns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": 'Concerns to address, e.g. ["acné", "manchas"].',
                },
                "current_ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Active ingredients already in the client's routine.",
                },
            },
            "required": ["skin_type", "concerns"],
        },
    },
]


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOL_SCHEMAS}}

    if method == "tools/call":
        params = message.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = TOOLS.get(tool_name)
        if tool is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool '{tool_name}'"},
            }
        try:
            output = tool(**arguments)
            is_error = False
        except Exception as exc:  # noqa: BLE001 - report tool failures to the client, not a crash
            output = str(exc)
            is_error = True
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": is_error},
        }

    if request_id is None:
        return None  # unrecognized notification -- nothing to reply with

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
