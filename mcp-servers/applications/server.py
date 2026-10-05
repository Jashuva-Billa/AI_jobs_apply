#!/usr/bin/env python3
"""
Applications MCP Server
Exposes tools for tailoring resumes factually, generating cover letters, and preparing safe question responses.
"""
import sys
import json
import asyncio

async def handle_tool_call(name: str, arguments: dict):
    if name == "tailor_application":
        return {
            "status": "PREPARED",
            "resume_version": "v1_tailored",
            "cover_letter": "Generated customized cover letter.",
            "questions_prepared": 4
        }
    raise ValueError(f"Unknown tool: {name}")

def main():
    print("Applications MCP Server running on stdio...", file=sys.stderr)
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
                                "name": "tailor_application",
                                "description": "Prepare a tailored application package.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "job_id": {"type": "string"},
                                        "candidate_id": {"type": "string"}
                                    },
                                    "required": ["job_id", "candidate_id"]
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
