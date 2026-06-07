#pragma once

#ifdef GHOSTRIGGER_ANIMATION_RETARGETING_EXPORTS
#define GHOSTRIGGER_ANIMATION_RETARGETING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ANIMATION_RETARGETING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_version();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_capabilities_json();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_owner_boundary_json();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_dependency_schema_json();
}