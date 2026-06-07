#pragma once

#ifdef GHOSTRIGGER_CAMERA_EXPORTS
#define GHOSTRIGGER_CAMERA_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CAMERA_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CAMERA_API const char* gr_camera_version();
GHOSTRIGGER_CAMERA_API const char* gr_camera_capabilities_json();
GHOSTRIGGER_CAMERA_API const char* gr_camera_owner_boundary_json();
GHOSTRIGGER_CAMERA_API const char* gr_camera_dependency_schema_json();
}