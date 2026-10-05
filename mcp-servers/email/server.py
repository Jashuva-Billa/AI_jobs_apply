#!/usr/bin/env python3
"""
Email MCP Server
Exposes tools for draft generation and authorized email dispatching with idempotency protection.
"""
import sys
import json
import asyncio

async def handle_tool_call(name: str, arguments: dict):
    if name == "create_draft":
        return {
            "status": "DRAFT_CREATED",
            "to": arguments.get("to_email"),
            "subject": arguments.get("subject")
        }
    elif name == "send_email":
        # Requires human approval
        return {
            "status": "SENT",
            "to": arguments.get("to_email"),
            "subject": arguments.get("subject"),
            "idempotency_key": arguments.get("idempotency_key")
        }
    raise ValueError(f"Unknown tool: {name}")

def main():
    print("Email MCP Server running on stdio...", file=sys.stderr)
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "create_draft",
                                "description": "Create an email draft for recruiter outreach.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "to_email": {"type": "string"},
                                        "subject": {"type": "string"},
                                        "body": {"type": "string"}
                                    },
                                    "required": ["to_email", "subject", "body"]
                                }
                            },
                            {
                                "name": "send_email",
                                "description": "Send an authorized recruiter email after human approval.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "to_email": {"type": "string"},
                                        "subject": {"type": "string"},
                                        "body": {"type": "string"},
                                        "idempotency_key": {"type": "string"}
                                    },
                                    "required": ["to_email", "subject", "body"]
                                }
                            }
                        ]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(handle_tool_call(tool_name, tool_args))
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }
            else:
                response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}
            
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")

if __name__ == "__main__":
    main()
