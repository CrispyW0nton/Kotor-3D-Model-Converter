#pragma once

#ifdef GHOSTRIGGER_DIAGNOSTICS_EXPORTS
#define GHOSTRIGGER_DIAGNOSTICS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_DIAGNOSTICS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_version();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_capabilities_json();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_owner_boundary_json();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_dependency_schema_json();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_normalize_resref(const char* value);
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_normalize_restype(const char* value);
GHOSTRIGGER_DIAGNOSTICS_API int gr_diagnostics_is_script_field(const char* field_name);
GHOSTRIGGER_DIAGNOSTICS_API int gr_diagnostics_is_dialog_field(const char* field_name);
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_missing_reference_issue_json(
    const char* kind,
    const char* resref,
    const char* restype,
    const char* owner_type,
    int owner_index,
    const char* field,
    const char* source_label);
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_contracts_schema_json();
}
