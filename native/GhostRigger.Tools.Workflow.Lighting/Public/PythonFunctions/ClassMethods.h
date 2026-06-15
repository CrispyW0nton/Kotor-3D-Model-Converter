#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::lighting {

#ifndef GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ghostriggerlight_from_object_line_60_d4b090e4_native();
const NativeFunctionImplementation& lightmapbakesettings_for_quality_line_123_5a1517f1_native();
const NativeFunctionImplementation& emitterconfig_from_node_line_218_43df53e1_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::lighting
