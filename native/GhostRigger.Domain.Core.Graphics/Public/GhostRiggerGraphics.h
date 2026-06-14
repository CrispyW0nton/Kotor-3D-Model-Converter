#pragma once

#ifdef GHOSTRIGGER_GRAPHICS_EXPORTS
#define GHOSTRIGGER_GRAPHICS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GRAPHICS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GRAPHICS_API const char* gr_graphics_version();
GHOSTRIGGER_GRAPHICS_API const char* gr_graphics_capabilities_json();
GHOSTRIGGER_GRAPHICS_API const char* gr_graphics_owner_boundary_json();
GHOSTRIGGER_GRAPHICS_API const char* gr_graphics_dependency_schema_json();
}