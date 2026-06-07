#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_CHARACTER_BUILDER_EXPORTS)
#define GR_TOOLS_CHARACTER_BUILDER_API __declspec(dllexport)
#else
#define GR_TOOLS_CHARACTER_BUILDER_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_CHARACTER_BUILDER_API
#endif

extern "C" {

GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_version();
GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_capabilities_json();
GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_owner_boundary_json();
GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_autofit_packet_schema_json();

}
