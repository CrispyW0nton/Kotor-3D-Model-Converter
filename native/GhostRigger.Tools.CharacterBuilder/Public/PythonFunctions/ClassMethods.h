#pragma once

#include <cstddef>

namespace ghostrigger::tools::characterbuilder {

#ifndef GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& autofitoverride_from_mapping_line_72_b939c173_native();
const NativeFunctionImplementation& creatureassembly_from_models_line_1193_dfce9043_native();
const NativeFunctionImplementation& creatureassembly_from_resrefs_line_1260_9de5d9fa_native();
const NativeFunctionImplementation& nativenodesnapshot_from_dict_line_77_23599e67_native();
const NativeFunctionImplementation& nativeskeletonsnapshot_from_dict_line_107_3c42a345_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::characterbuilder
