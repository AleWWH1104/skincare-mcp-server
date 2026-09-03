"""Skincare recommendation MCP server -- stdio transport adapter.

Reads newline-delimited JSON-RPC 2.0 requests from stdin and writes
responses to stdout, per the MCP transport spec. The protocol logic
itself (tool dispatch, schemas) lives in mcp_protocol.py, shared with
the Streamable HTTP transport adapter in http_server.py.
"""

import json
import sys

from mcp_protocol import handle_message


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
