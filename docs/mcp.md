# Model Context Protocol (MCP) Architecture

The platform supports both internal tool adapters and standalone **FastMCP / JSON-RPC 2.0 stdio** tool servers.

## Implemented MCP Servers
1. **Job Search MCP (`mcp-servers/jobs/server.py`)**:
   - `search_jobs`: Queries multi-source listings with role and skill parameters.
2. **Email MCP (`mcp-servers/email/server.py`)**:
   - `create_draft`: Prepares recruiter outreach draft.
   - `send_email`: Sends authorized email after explicit user approval.
3. **Recruiters MCP (`mcp-servers/recruiters/server.py`)**:
   - `discover_recruiter`: Looks up verified talent acquisition partners.
4. **Applications MCP (`mcp-servers/applications/server.py`)**:
   - `tailor_application`: Assembles tailored resume version, cover letter, and safe answers.
