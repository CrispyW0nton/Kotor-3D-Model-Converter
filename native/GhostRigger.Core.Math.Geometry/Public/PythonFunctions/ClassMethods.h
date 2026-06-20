#pragma once

#include <cstddef>

namespace ghostrigger::core::geometry {

#ifndef GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& kotormodel_load_line_1713_06efb4df_native();
const NativeFunctionImplementation& characterscene_hook_list_for_line_2059_3faac002_native();
const NativeFunctionImplementation& characterscene_facial_bone_list_for_line_2072_1a08165b_native();
const NativeFunctionImplementation& characterscene_from_dict_line_2196_7e1623ef_native();
const NativeFunctionImplementation& characterscene_from_json_line_2314_e011a172_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::geometry
