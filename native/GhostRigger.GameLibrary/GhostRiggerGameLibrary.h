#pragma once

#ifdef GHOSTRIGGER_GAME_LIBRARY_EXPORTS
#define GHOSTRIGGER_GAME_LIBRARY_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GAME_LIBRARY_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GAME_LIBRARY_API const char* gr_game_library_version();
GHOSTRIGGER_GAME_LIBRARY_API const char* gr_game_library_capabilities_json();
GHOSTRIGGER_GAME_LIBRARY_API const char* gr_game_library_owner_boundary_json();
GHOSTRIGGER_GAME_LIBRARY_API const char* gr_game_library_dependency_schema_json();
}