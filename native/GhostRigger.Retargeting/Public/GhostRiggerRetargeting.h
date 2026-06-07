#pragma once

#ifdef GHOSTRIGGER_RETARGETING_EXPORTS
#define GHOSTRIGGER_RETARGETING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_RETARGETING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_version();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_capabilities_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_owner_boundary_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_dependency_schema_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_coerce_mode(const char* mode);
GHOSTRIGGER_RETARGETING_API int gr_retargeting_is_kotor_output_mode(const char* mode);
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_mode_specs_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_coerce_kotor_output_name_mode(const char* mode);
GHOSTRIGGER_RETARGETING_API int gr_retargeting_validate_custom_kotor_animation_name(
    const char* name,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_RETARGETING_API int gr_retargeting_validate_unreal_clip_name(
    const char* name,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_contracts_schema_json();
}
