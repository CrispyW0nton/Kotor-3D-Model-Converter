#pragma once

#ifdef GHOSTRIGGER_GAME_EXPORTS
#define GHOSTRIGGER_GAME_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GAME_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GAME_API const char* gr_game_version();
GHOSTRIGGER_GAME_API const char* gr_game_capabilities_json();
GHOSTRIGGER_GAME_API const char* gr_game_owner_boundary_json();
GHOSTRIGGER_GAME_API const char* gr_game_dependency_schema_json();
GHOSTRIGGER_GAME_API const char* gr_game_resource_type_name(int resource_type);
GHOSTRIGGER_GAME_API const char* gr_game_resource_type_extension(int resource_type);
GHOSTRIGGER_GAME_API const char* gr_game_resource_type_contracts_schema_json();
}
