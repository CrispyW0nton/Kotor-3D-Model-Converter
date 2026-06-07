#pragma once

#ifdef GHOSTRIGGER_PORTS_EXPORTS
#define GHOSTRIGGER_PORTS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_PORTS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_PORTS_API const char* gr_ports_version();
GHOSTRIGGER_PORTS_API const char* gr_ports_capabilities_json();
GHOSTRIGGER_PORTS_API const char* gr_ports_owner_boundary_json();
GHOSTRIGGER_PORTS_API const char* gr_ports_dependency_schema_json();
}