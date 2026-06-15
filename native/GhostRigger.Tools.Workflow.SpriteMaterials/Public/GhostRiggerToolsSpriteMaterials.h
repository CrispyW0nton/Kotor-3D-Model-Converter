#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_SPRITE_MATERIALS_EXPORTS)
#define GR_TOOLS_SPRITE_MATERIALS_API __declspec(dllexport)
#else
#define GR_TOOLS_SPRITE_MATERIALS_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_SPRITE_MATERIALS_API
#endif

extern "C" {

GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_version();
GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_capabilities_json();
GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_owner_boundary_json();
GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_material_packet_schema_json();

}
