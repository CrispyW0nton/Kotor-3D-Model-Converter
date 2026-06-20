#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_SEQUENCE_EDITOR_EXPORTS)
#define GR_TOOLS_SEQUENCE_EDITOR_API __declspec(dllexport)
#else
#define GR_TOOLS_SEQUENCE_EDITOR_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_SEQUENCE_EDITOR_API
#endif

extern "C" {

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_version();
GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_capabilities_json();
GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_owner_boundary_json();
GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_sequence_packet_schema_json();

}
