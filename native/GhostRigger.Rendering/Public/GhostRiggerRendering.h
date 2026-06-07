#pragma once

#ifdef GHOSTRIGGER_RENDERING_EXPORTS
#define GHOSTRIGGER_RENDERING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_RENDERING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_RENDERING_API const char* gr_rendering_version();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_capabilities_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_owner_boundary_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_dependency_schema_json();
}