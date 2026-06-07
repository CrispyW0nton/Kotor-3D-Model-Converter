#pragma once

#ifdef GHOSTRIGGER_TEMPLATES_EXPORTS
#define GHOSTRIGGER_TEMPLATES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_TEMPLATES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_version();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_capabilities_json();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_owner_boundary_json();
GHOSTRIGGER_TEMPLATES_API const char* gr_templates_dependency_schema_json();
}