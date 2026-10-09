#!/usr/bin/env python3
"""
Email MCP Server
Exposes tools for draft generation and authorized email dispatching with real SMTP delivery.
"""
import sys
import json
import asyncio
import os
import smtplib
from email.mime.text import MIMEText

async def handle_tool_call(name: str, arguments: dict):
    if name == "create_draft":
        return {
            "status": "DRAFT_CREATED",
            "to": arguments.get("to_email"),
            "subject": arguments.get("subject")
        }
    elif name == "send_email":
        # Requires human approval. Never report SENT unless SMTP accepted the message.
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASSWORD")
        sender = os.getenv("EMAIL_FROM") or user

        if not (host and user and password and sender):
            return {
                "status": "NOT_SENT",
                "reason": "SMTP_NOT_CONFIGURED",
                "to": arguments.get("to_email")
            }

        msg = MIMEText(arguments.get("body", ""), "plain")
        msg["From"] = sender
        msg["To"] = arguments.get("to_email")
        msg["Subject"] = arguments.get("subject", "")

        try:
            server = smtplib.SMTP(host, port, timeout=20)
            try:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
            finally:
                server.quit()

            return {
                "status": "SENT",
                "to": arguments.get("to_email"),
                "subject": arguments.get("subject"),
                "idempotency_key": arguments.get("idempotency_key")
            }
        except Exception as exc:
            return {
                "status": "FAILED",
                "to": arguments.get("to_email"),
                "error": str(exc)
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
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result)}
                        ]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "Method not found"}
                }

            print(json.dumps(response), flush=True)
        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": req_id if "req_id" in locals() else None,
                "error": {"code": -32000, "message": str(e)}
            }), flush=True)

if __name__ == "__main__":
    main()
