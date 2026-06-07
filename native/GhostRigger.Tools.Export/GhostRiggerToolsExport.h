#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_EXPORT_EXPORTS)
#define GR_TOOLS_EXPORT_API __declspec(dllexport)
#else
#define GR_TOOLS_EXPORT_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_EXPORT_API
#endif

extern "C" {

GR_TOOLS_EXPORT_API const char* gr_tools_export_version();
GR_TOOLS_EXPORT_API const char* gr_tools_export_capabilities_json();
GR_TOOLS_EXPORT_API const char* gr_tools_export_owner_boundary_json();
GR_TOOLS_EXPORT_API const char* gr_tools_export_preflight_packet_schema_json();

}
