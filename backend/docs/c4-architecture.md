# C4 Architecture Diagrams

This document captures the current architecture of the Agent Platform API using the C4 model.
It is derived from the backend code and deployment config in this repository.

## Context

```mermaid
C4Context
title Agent Platform - System Context
Person(apiUser, "API User", "Calls REST API using JWT or API key")
System_Boundary(agentsApp, "Agent Platform") {
  System(api, "Agent Platform API", "FastAPI backend for agents, tools, runs")
}
System_Ext(llm, "LLM Provider", "OpenAI-compatible API via PydanticAI")
System_Ext(toolApis, "Tool HTTP Endpoints", "External APIs invoked by tools")
System_Ext(sqns, "SQNS CRM", "Optional external integration")

Rel(apiUser, api, "Uses", "HTTPS/JSON")
Rel(api, llm, "Generates responses", "HTTPS")
Rel(api, toolApis, "Executes tools", "HTTPS")
Rel(api, sqns, "Syncs data", "HTTPS")
```

## Containers

```mermaid
C4Container
title Agent Platform - Containers
Person(apiUser, "API User", "REST client")
System_Boundary(agentsApp, "Agent Platform") {
  Container(nginx, "Nginx", "nginx", "Reverse proxy and TLS termination")
  Container(api, "API Service", "FastAPI", "Runs agents, tools, runs API")
  ContainerDb(db, "PostgreSQL", "Postgres 16", "Primary data store")
  Container(redis, "Redis", "Redis 7", "Rate limiting state")
  Container(pgadmin, "pgAdmin", "pgAdmin 8", "DB admin UI")
  Container(toolMock, "Tool Mock", "FastAPI", "Dev/test tool endpoint")
}
System_Ext(llm, "LLM Provider", "OpenAI-compatible")
System_Ext(toolApis, "External Tool APIs", "HTTP webhooks")
System_Ext(sqns, "SQNS CRM", "External integration")

Rel(apiUser, nginx, "Uses", "HTTPS")
Rel(nginx, api, "Proxies", "HTTP")
Rel(nginx, pgadmin, "Proxies /postgres", "HTTP")
Rel(api, db, "Reads/Writes", "SQLAlchemy async")
Rel(api, redis, "Rate limiting", "Redis")
Rel(api, toolApis, "Executes tools", "HTTPS")
Rel(api, llm, "LLM calls", "HTTPS")
Rel(api, sqns, "CRM sync", "HTTPS")
Rel(api, toolMock, "Calls in dev", "HTTP")
```

## Components (API Service)

```mermaid
C4Component
title Agent Platform API - Components
Container_Boundary(api, "API Service") {
  Component(apiRouters, "API Routers", "FastAPI routers", "Auth, agents, tools, bindings, runs, api keys, credentials")
  Component(runtime, "Runtime Service", "Python", "Builds agents and orchestrates tool calls")
  Component(toolExecutor, "Tool Executor", "Python", "HTTP tool execution, validation, retries")
  Component(credentials, "Credentials Service", "Python", "Encrypts and decrypts tool credentials")
  Component(secrets, "Secrets Service", "Python", "Resolves secrets from env")
  Component(audit, "Audit Service", "Python", "Writes audit logs")
  Component(security, "Security", "Python", "JWT decoding and auth context")
  Component(limiter, "Rate Limiter", "SlowAPI + Redis", "Per-tenant limits")
  ComponentDb(models, "DB Models", "SQLAlchemy", "Agents, tools, bindings, runs, users")
  Component(dbSession, "DB Session", "SQLAlchemy", "Async session factory")
}

ContainerDb(db, "PostgreSQL", "Postgres 16", "Primary data store")
Container(redis, "Redis", "Redis 7", "Rate limiting state")
System_Ext(llm, "LLM Provider", "OpenAI-compatible")
System_Ext(toolApis, "External Tool APIs", "HTTP webhooks")
System_Ext(sqns, "SQNS CRM", "External integration")

Rel(apiRouters, security, "Authenticates/authorizes", "")
Rel(apiRouters, limiter, "Rate limits", "")
Rel(apiRouters, runtime, "Runs agents", "")
Rel(apiRouters, toolExecutor, "Tool test calls", "")
Rel(apiRouters, dbSession, "CRUD via", "")
Rel(runtime, models, "Reads/Writes", "")
Rel(runtime, toolExecutor, "Invokes", "")
Rel(runtime, llm, "Prompts", "HTTPS")
Rel(runtime, sqns, "Optional tools", "HTTPS")
Rel(toolExecutor, toolApis, "Executes", "HTTPS")
Rel(toolExecutor, credentials, "Uses", "")
Rel(credentials, secrets, "Resolves", "")
Rel(dbSession, db, "Connects", "")
Rel(limiter, redis, "Stores counters", "")
Rel(audit, models, "Writes", "")
```

## Code (Agent Execution)

```mermaid
classDiagram
class Agent {
  +UUID id
  +string name
  +string system_prompt
  +string model
  +dict llm_params
}
class Tool {
  +UUID id
  +string name
  +dict input_schema
  +string execution_type
  +string endpoint
  +string auth_type
}
class AgentToolBinding {
  +UUID id
  +string permission_scope
  +int timeout_ms
  +list allowed_domains
  +string secrets_ref
}
class Run {
  +UUID id
  +string status
  +string input_message
  +string output_message
}
class RuntimeService {
  +run_agent_with_tools(...)
  +_build_agent(...)
  +_build_tool_wrapper(...)
  +_wrap_tool_signature(...)
}
class ToolExecutor {
  +execute_tool_call(...)
}
RuntimeService --> Agent : uses
RuntimeService --> Tool : uses
RuntimeService --> AgentToolBinding : uses
RuntimeService --> Run : writes
RuntimeService --> ToolExecutor : calls
ToolExecutor --> Tool : uses endpoint/auth
```

## Sources

- `README.md`
- `docker-compose.yml`
- `backend/app/main.py`
- `backend/app/api/routers/`
- `backend/app/services/runtime.py`
- `backend/app/services/tool_executor.py`
- `backend/app/db/models/`
- `backend/app/core/`
