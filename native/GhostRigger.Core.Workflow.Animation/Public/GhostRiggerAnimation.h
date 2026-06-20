#pragma once

#ifdef GHOSTRIGGER_ANIMATION_EXPORTS
#define GHOSTRIGGER_ANIMATION_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ANIMATION_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ANIMATION_API const char* gr_animation_version();
GHOSTRIGGER_ANIMATION_API const char* gr_animation_capabilities_json();
GHOSTRIGGER_ANIMATION_API const char* gr_animation_owner_boundary_json();
GHOSTRIGGER_ANIMATION_API const char* gr_animation_dependency_schema_json();
}