#pragma once

#ifdef GHOSTRIGGER_RETARGETING_EXPORTS
#define GHOSTRIGGER_RETARGETING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_RETARGETING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_version();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_capabilities_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_owner_boundary_json();
GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_dependency_schema_json();
}