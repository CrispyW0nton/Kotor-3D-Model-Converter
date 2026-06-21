#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_RETARGETING_EXPORTS)
#define GR_TOOLS_RETARGETING_API __declspec(dllexport)
#else
#define GR_TOOLS_RETARGETING_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_RETARGETING_API
#endif

extern "C" {

GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_version();
GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_capabilities_json();
GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_owner_boundary_json();
GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_solve_packet_schema_json();

}
