#pragma once

#ifdef GHOSTRIGGER_CHARACTERS_EXPORTS
#define GHOSTRIGGER_CHARACTERS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CHARACTERS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CHARACTERS_API const char* gr_characters_version();
GHOSTRIGGER_CHARACTERS_API const char* gr_characters_capabilities_json();
GHOSTRIGGER_CHARACTERS_API const char* gr_characters_owner_boundary_json();
GHOSTRIGGER_CHARACTERS_API const char* gr_characters_dependency_schema_json();
}