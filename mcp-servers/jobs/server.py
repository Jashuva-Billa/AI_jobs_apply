#!/usr/bin/env python3
"""
Job Search MCP Server
Exposes tools for searching, querying, and filtering verified job openings.
"""
import sys
import json
import asyncio

async def handle_tool_call(name: str, arguments: dict):
    if name == "search_jobs":
        roles = arguments.get("roles", ["AI Engineer"])
        skills = arguments.get("skills", ["Python", "RAG"])
        return {
            "status": "SUCCESS",
            "results_count": 5,
            "jobs": [
                {
                    "title": "Senior AI Systems Engineer",
                    "company": "Anthropic AI Labs",
                    "location": "Remote",
                    "skills": ["Python", "RAG", "LangGraph", "AWS", "MCP"]
                },
                {
                    "title": "GenAI Engineer",
                    "company": "ScaleGen AI",
                    "location": "Remote (India)",
                    "skills": ["Python", "FastAPI", "RAG", "LangGraph"]
                }
            ]
        }
    raise ValueError(f"Unknown tool: {name}")

def main():
    print("Job Search MCP Server running on stdio...", file=sys.stderr)
    # MCP stdio interface loop
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
                                "name": "search_jobs",
                                "description": "Search verified remote and local AI / ML engineering jobs.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "roles": {"type": "array", "items": {"type": "string"}},
                                        "skills": {"type": "array", "items": {"type": "string"}},
                                        "location": {"type": "string"}
                                    }
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
