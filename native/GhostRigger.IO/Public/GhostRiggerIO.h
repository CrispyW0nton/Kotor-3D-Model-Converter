#pragma once

#ifdef GHOSTRIGGER_IO_EXPORTS
#define GHOSTRIGGER_IO_API __declspec(dllexport)
#else
#define GHOSTRIGGER_IO_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_IO_API const char* gr_io_version();
GHOSTRIGGER_IO_API const char* gr_io_capabilities_json();
GHOSTRIGGER_IO_API const char* gr_io_owner_boundary_json();
GHOSTRIGGER_IO_API const char* gr_io_dependency_schema_json();
GHOSTRIGGER_IO_API const char* gr_io_fbx_sdk_download_url();
GHOSTRIGGER_IO_API const char* gr_io_fbx_sdk_licence_notice();
GHOSTRIGGER_IO_API const char* gr_io_fbx_sdk_recommended_fix(const char* error);
GHOSTRIGGER_IO_API const char* gr_io_fbx_sdk_settings_contracts_schema_json();
}
