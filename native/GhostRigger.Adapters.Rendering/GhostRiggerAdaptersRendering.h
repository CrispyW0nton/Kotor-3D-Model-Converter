#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_RENDERING_EXPORTS
#define GHOSTRIGGER_ADAPTERS_RENDERING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_RENDERING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_RENDERING_API const char* gr_adapters_rendering_version();
GHOSTRIGGER_ADAPTERS_RENDERING_API const char* gr_adapters_rendering_capabilities_json();
GHOSTRIGGER_ADAPTERS_RENDERING_API const char* gr_adapters_rendering_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_RENDERING_API const char* gr_adapters_rendering_dependency_schema_json();
}