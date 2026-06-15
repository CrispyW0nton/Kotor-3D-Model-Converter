#pragma once

#ifdef GHOSTRIGGER_WORKFLOW_EXPORTS
#define GHOSTRIGGER_WORKFLOW_API __declspec(dllexport)
#else
#define GHOSTRIGGER_WORKFLOW_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_version();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_capabilities_json();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_owner_boundary_json();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_dependency_schema_json();
GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_ext_of(const char* path, char* output, unsigned long long output_size);
GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_resref_from_path(const char* path, char* output, unsigned long long output_size);
GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_safe_resref(
    const char* text,
    const char* fallback,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_banner_key_for_counts(
    int errors,
    int warnings,
    int infos,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_summary_for_counts(
    int errors,
    int warnings,
    int infos,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_base_schema_json();
}
