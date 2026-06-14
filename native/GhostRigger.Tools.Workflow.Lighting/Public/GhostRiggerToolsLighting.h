#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_LIGHTING_EXPORTS)
#define GR_TOOLS_LIGHTING_API __declspec(dllexport)
#else
#define GR_TOOLS_LIGHTING_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_LIGHTING_API
#endif

extern "C" {

GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_version();
GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_capabilities_json();
GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_owner_boundary_json();
GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_light_packet_schema_json();

}
