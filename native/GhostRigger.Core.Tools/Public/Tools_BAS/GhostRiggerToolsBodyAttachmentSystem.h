#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_BODY_ATTACHMENT_SYSTEM_EXPORTS)
#define GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API __declspec(dllexport)
#else
#define GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API
#endif

extern "C" {

GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_version();
GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_capabilities_json();
GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_owner_boundary_json();
GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_attachment_packet_schema_json();

}
