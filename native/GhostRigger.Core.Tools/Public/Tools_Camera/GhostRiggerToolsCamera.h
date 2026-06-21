#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_CAMERA_EXPORTS)
#define GR_TOOLS_CAMERA_API __declspec(dllexport)
#else
#define GR_TOOLS_CAMERA_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_CAMERA_API
#endif

extern "C" {

GR_TOOLS_CAMERA_API const char* gr_tools_camera_version();
GR_TOOLS_CAMERA_API const char* gr_tools_camera_capabilities_json();
GR_TOOLS_CAMERA_API const char* gr_tools_camera_owner_boundary_json();
GR_TOOLS_CAMERA_API const char* gr_tools_camera_camera_packet_schema_json();

}
