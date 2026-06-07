#pragma once

#if defined(_WIN32)
#if defined(RUNTIME_SHARED_RESOURCES_EXPORTS)
#define GR_RUNTIME_SHARED_RESOURCES_API __declspec(dllexport)
#else
#define GR_RUNTIME_SHARED_RESOURCES_API __declspec(dllimport)
#endif
#else
#define GR_RUNTIME_SHARED_RESOURCES_API
#endif

extern "C" {

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_version();
GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_capabilities_json();
GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_id_schema_json();
GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_residency_schema_json();
GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_upload_packet_schema_json();
GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_transition_packet_schema_json();

}
