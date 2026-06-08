#pragma once

#ifdef GHOSTRIGGER_TEMPLATES_EXPORTS
#define GHOSTRIGGER_TEMPLATES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_TEMPLATES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_version();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_capabilities_json();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_owner_boundary_json();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_dependency_schema_json();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_normalize_game_version(const char* game_version);
GHOSTRIGGER_TEMPLATES_API int gr_templates_humanoid_bone_count(const char* game_version);
GHOSTRIGGER_TEMPLATES_API int gr_templates_humanoid_animation_slot_count(const char* game_version);
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_humanoid_rig_source(const char* game_version);
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_detect_twoda_format(const unsigned char* data, unsigned int size);
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_twoda_cell_or_default(const char* value, const char* fallback);
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_split_twoda_line_json(const char* line);
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_contracts_schema_json();
}
