#pragma once

#include "GhostRiggerAdaptersScripts.h"

#include <string>

namespace ghostrigger::adapters::scripting {

const char* default_unavailable_reason();
std::string unavailable_validation_issue_json(const char* source, const char* game, const char* reason);
std::string unavailable_compile_result_json(const char* source, const char* game, const char* reason);

} // namespace ghostrigger::adapters::scripting

extern "C" {
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_default_reason();
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_issue_json(
    const char* source,
    const char* game,
    const char* reason
);
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_compile_result_json(
    const char* source,
    const char* game,
    const char* reason
);
}
