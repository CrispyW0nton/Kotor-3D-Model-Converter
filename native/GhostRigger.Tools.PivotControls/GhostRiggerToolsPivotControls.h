#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_PIVOT_CONTROLS_EXPORTS)
#define GR_TOOLS_PIVOT_CONTROLS_API __declspec(dllexport)
#else
#define GR_TOOLS_PIVOT_CONTROLS_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_PIVOT_CONTROLS_API
#endif

extern "C" {

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_version();
GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_capabilities_json();
GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_owner_boundary_json();
GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_pivot_packet_schema_json();

}
