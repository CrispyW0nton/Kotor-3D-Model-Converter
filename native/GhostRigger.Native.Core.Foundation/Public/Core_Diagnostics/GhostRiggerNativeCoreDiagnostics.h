#pragma once

#if defined(_WIN32)
#if defined(NATIVE_CORE_DIAGNOSTICS_EXPORTS)
#define GR_NATIVE_CORE_DIAGNOSTICS_API __declspec(dllexport)
#else
#define GR_NATIVE_CORE_DIAGNOSTICS_API __declspec(dllimport)
#endif
#else
#define GR_NATIVE_CORE_DIAGNOSTICS_API
#endif

extern "C" {

GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_version();
GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_capabilities_json();
GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_record_schema_json();
GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_make_record_json(
    int severity,
    const char* system,
    const char* code,
    const char* message);

}
