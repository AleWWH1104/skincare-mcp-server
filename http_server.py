"""Skincare recommendation MCP server -- Streamable HTTP transport adapter.

Exposes the same tool logic as server.py (stdio) over a single HTTP
endpoint, so this server can run remotely/containerized instead of as a
local stdio subprocess. Implements the MCP "Streamable HTTP" transport
by hand -- one POST endpoint accepting a JSON-RPC 2.0 message per
request -- using only the standard library's http.server.
"""

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp_protocol import handle_message

MCP_PATH = "/mcp"


class MCPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    _sessions: set[str] = set()

    def _send_json(self, status: int, payload: dict | None, session_id: str | None = None) -> None:
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != MCP_PATH:
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        try:
            message = json.loads(raw_body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        method = message.get("method")

        # The client has no session yet on its first call, so `initialize`
        # is the one method allowed without a known Mcp-Session-Id.
        if method == "initialize":
            response = handle_message(message)
            new_session_id = uuid.uuid4().hex
            self._sessions.add(new_session_id)
            self._send_json(200, response, session_id=new_session_id)
            return

        session_id = self.headers.get("Mcp-Session-Id")
        if session_id is not None and session_id not in self._sessions:
            self._send_json(404, {"error": "unknown session"})
            return

        response = handle_message(message)
        if response is None:
            self._send_json(202, None)  # notification: no body expected
        else:
            self._send_json(200, response)

    def log_message(self, format_str: str, *args) -> None:
        pass  # keep stdout clean -- this isn't MCP protocol traffic


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MCPRequestHandler)
    print(f"skincare MCP server (HTTP) listening on http://0.0.0.0:{port}{MCP_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
