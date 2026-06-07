#pragma once

#ifdef GHOSTRIGGER_KOTOR_MCP_EXPORTS
#define GHOSTRIGGER_KOTOR_MCP_API __declspec(dllexport)
#else
#define GHOSTRIGGER_KOTOR_MCP_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_KOTOR_MCP_API const char* gr_kotor_mcp_version();
GHOSTRIGGER_KOTOR_MCP_API const char* gr_kotor_mcp_capabilities_json();
GHOSTRIGGER_KOTOR_MCP_API const char* gr_kotor_mcp_owner_boundary_json();
GHOSTRIGGER_KOTOR_MCP_API const char* gr_kotor_mcp_dependency_schema_json();
}