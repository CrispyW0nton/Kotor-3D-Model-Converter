#pragma once

#ifdef GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_EXPORTS
#define GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_version();
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_capabilities_json();
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_owner_boundary_json();
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_dependency_schema_json();
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_unavailable_default_reason();
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_unavailable_issue_json(
    const char* source,
    const char* game,
    const char* reason
);
GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_unavailable_compile_result_json(
    const char* source,
    const char* game,
    const char* reason
);
}
