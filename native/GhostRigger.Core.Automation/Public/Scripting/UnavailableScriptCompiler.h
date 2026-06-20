#pragma once

#include "Scripting/GhostRiggerCoreAutomationScripting.h"

#include <string>

namespace ghostrigger::core::automation::scripting {

const char* default_unavailable_reason();
std::string unavailable_validation_issue_json(const char* source, const char* game, const char* reason);
std::string unavailable_compile_result_json(const char* source, const char* game, const char* reason);

} // namespace ghostrigger::core::automation::scripting

extern "C" {
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
