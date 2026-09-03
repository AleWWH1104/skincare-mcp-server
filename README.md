# Skincare Recommendation MCP Server

An MCP (Model Context Protocol) server that helps recommend skincare products based on a client's skin type and concerns, checks for known ingredient conflicts with their current routine, and looks up stock/pricing or alternatives from a simulated store inventory.

Built for the "Uso de un protocolo existente" project (CC3067 Redes, Universidad del Valle de Guatemala). Runs locally over stdio — no network access, no API keys required.

## Features

- Search a product catalog by skin type and/or skincare concern
- Look up full details (price, stock, active ingredients) for a specific product
- Find in-stock alternatives that share an active ingredient with an out-of-stock or discontinued product
- Check whether a candidate product's active ingredients conflict with a client's current routine, using a rule set based on real dermatological interactions (e.g. retinol + AHA acids, benzoyl peroxide + tretinoin)
- End-to-end recommendation: filter the catalog by skin type/concerns and flag conflicts against the current routine in one call

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python version and dependencies — nothing else to install manually)
- [Docker](https://docs.docker.com/get-docker/) — only needed to run the remote (HTTP) transport in a container

## Installation

```bash
git clone <https://github.com/AleWWH1104/skincare-mcp-server.git>
cd skincare-mcp-server
uv sync
```

`uv sync` reads `pyproject.toml`/`uv.lock` and creates an isolated `.venv` with the exact dependency versions this server was built and tested against.

## Running it standalone (for testing)

Use the official [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to call each tool by hand from a web UI, without needing an LLM host:

```bash
npx @modelcontextprotocol/inspector uv run python server.py
```

## Connecting it to an MCP host

This server ships two transport adapters over the same tool logic (`mcp_protocol.py`) — a local one and a remote one.

### Local (stdio)

```bash
uv run --directory /absolute/path/to/skincare-mcp-server python server.py
```

Example host-side config entry (Python, matching this project's own host):

```python
MCPServerConfig(
    name="skincare",
    command="uv",
    args=["run", "--directory", "/absolute/path/to/skincare-mcp-server", "python", "server.py"],
)
```

### Remote (Streamable HTTP, via Docker)

`http_server.py` exposes the same tools over a single HTTP endpoint using the MCP "Streamable HTTP" transport (one `POST /mcp` per JSON-RPC message), implemented by hand with only the standard library — no MCP SDK, no web framework.

Build and run the container:

```bash
docker build -t skincare-mcp-server .
docker run --rm -p 8080:8080 skincare-mcp-server
```

The server listens on `PORT` (default `8080`), so it's ready to deploy to any container-based cloud service (Cloud Run, Fly.io, Render, etc.) that sets `PORT` for you.

Example host-side config entry for the remote transport:

```python
MCPServerConfig(
    name="skincare_remote",
    transport="http",
    url="http://localhost:8080/mcp",
)
```

## Data model

Several tools return a `Product` object:

| Field                | Type     | Notes                                                                          |
| -------------------- | -------- | ------------------------------------------------------------------------------ |
| `id`                 | string   | e.g. `"sr-001"`                                                                |
| `name`               | string   |                                                                                |
| `brand`              | string   |                                                                                |
| `category`           | string   | `"limpiador"`, `"sérum"`, `"tratamiento"`, `"hidratante"`, `"protector solar"` |
| `skin_types`         | string[] | e.g. `"grasa"`, `"seca"`, `"mixta"`, `"sensible"`, `"normal"`                  |
| `concerns`           | string[] | e.g. `"acné"`, `"manchas"`, `"arrugas"`, `"sensibilidad"`, `"hidratación"`     |
| `active_ingredients` | string[] | e.g. `"niacinamida"`, `"retinol"`                                              |
| `price`              | number   |                                                                                |
| `stock`              | integer  | `0` means out of stock                                                         |
| `description`        | string   |                                                                                |

## Tools

### `search_products`

Search the catalog by skin type and/or concern.

**Parameters**

| Name            | Type    | Required | Default | Description                                     |
| --------------- | ------- | -------- | ------- | ----------------------------------------------- |
| `skin_type`     | string  | no       | `""`    | e.g. `"grasa"`. Empty string skips this filter. |
| `concern`       | string  | no       | `""`    | e.g. `"acné"`. Empty string skips this filter.  |
| `in_stock_only` | boolean | no       | `true`  | Exclude products with `stock == 0`.             |

**Returns:** `Product[]`

**Example**

```json
{ "skin_type": "grasa", "concern": "acné" }
```

```json
[
    { "id": "cl-001", "name": "Gel Limpiador Purificante", "brand": "DermaPura", "stock": 14, "...": "..." },
    { "id": "sr-001", "name": "Sérum Niacinamida 10%", "brand": "PureLab", "stock": 9, "...": "..." }
]
```

---

### `get_product_details`

Full details for one product by id.

**Parameters**

| Name         | Type   | Required |
| ------------ | ------ | -------- |
| `product_id` | string | yes      |

**Returns:** `Product`, or `{"error": "..."}` if the id doesn't exist.

**Example**

```json
{ "product_id": "sr-001" }
```

```json
{
    "id": "sr-001",
    "name": "Sérum Niacinamida 10%",
    "brand": "PureLab",
    "price": 145.0,
    "stock": 9,
    "active_ingredients": ["niacinamida"]
}
```

---

### `find_alternatives`

Other in-stock products sharing at least one active ingredient with the given product — for when it's out of stock or the client wants a different brand.

**Parameters**

| Name            | Type    | Required | Default |
| --------------- | ------- | -------- | ------- |
| `product_id`    | string  | yes      |         |
| `in_stock_only` | boolean | no       | `true`  |

**Returns:** `Product[]`

**Example** — `sr-002` (a vitamin C serum) is out of stock:

```json
{ "product_id": "sr-002" }
```

```json
[{ "id": "sr-006", "name": "Sérum Vitamina C 10% Suave", "brand": "GlowCo", "stock": 10 }]
```

---

### `check_ingredient_conflicts`

Check a candidate product's active ingredients against ingredients the client is already using.

**Parameters**

| Name                    | Type     | Required | Description                                         |
| ----------------------- | -------- | -------- | --------------------------------------------------- |
| `current_ingredients`   | string[] | yes      | Active ingredients in the client's current routine. |
| `candidate_ingredients` | string[] | yes      | Active ingredients of the product being considered. |

**Returns:** array of conflicts, empty if none found:

```json
[
    {
        "ingredients": ["retinol", "ácido glicólico"],
        "severity": "avoid",
        "reason": "Combining retinol with AHA exfoliants in the same routine significantly increases the risk of irritation, dryness and peeling.",
        "recommendation": "Alternate nights: retinol one night, AHA/BHA exfoliant the next, never the same day."
    }
]
```

**Example call**

```json
{ "current_ingredients": ["retinol"], "candidate_ingredients": ["ácido glicólico"] }
```

---

### `recommend_products`

End-to-end recommendation: filter the catalog by skin type/concerns, and flag conflicts against the client's current routine for every match.

**Parameters**

| Name                  | Type     | Required | Description                                         |
| --------------------- | -------- | -------- | --------------------------------------------------- |
| `skin_type`           | string   | yes      | e.g. `"grasa"`.                                     |
| `concerns`            | string[] | yes      | e.g. `["acné", "manchas"]`.                         |
| `current_ingredients` | string[] | no       | Active ingredients already in the client's routine. |

**Returns**

```json
{
    "recommendations": [
        {
            "product": { "id": "sr-001", "name": "Sérum Niacinamida 10%", "...": "..." },
            "conflicts": [],
            "safe_to_combine": true
        },
        {
            "product": { "id": "tr-002", "name": "Exfoliante Químico AHA/BHA", "...": "..." },
            "conflicts": [{ "severity": "caution", "...": "..." }],
            "safe_to_combine": false
        }
    ]
}
```

## Notes

- The product catalog (`data/inventory.json`) is simulated data for this project, not a real store.
- The ingredient interaction rules (`data/ingredient_rules.json`) are simplified from real, commonly cited dermatological guidance (e.g. retinol/AHA, benzoyl peroxide/tretinoin). This is a demo tool, not medical or professional skincare advice.
