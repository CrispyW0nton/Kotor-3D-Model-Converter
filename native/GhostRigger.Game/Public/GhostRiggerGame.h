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
}