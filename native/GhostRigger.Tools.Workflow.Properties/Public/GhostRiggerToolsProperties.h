#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_PROPERTIES_EXPORTS)
#define GR_TOOLS_PROPERTIES_API __declspec(dllexport)
#else
#define GR_TOOLS_PROPERTIES_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_PROPERTIES_API
#endif

extern "C" {

GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_version();
GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_capabilities_json();
GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_owner_boundary_json();
GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_property_packet_schema_json();

}
