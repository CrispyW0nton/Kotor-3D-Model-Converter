#pragma once

#ifdef GHOSTRIGGER_INFRA_EXPORTS
#define GHOSTRIGGER_INFRA_API __declspec(dllexport)
#else
#define GHOSTRIGGER_INFRA_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_INFRA_API const char* gr_infra_version();
GHOSTRIGGER_INFRA_API const char* gr_infra_capabilities_json();
GHOSTRIGGER_INFRA_API const char* gr_infra_owner_boundary_json();
GHOSTRIGGER_INFRA_API const char* gr_infra_dependency_schema_json();
}