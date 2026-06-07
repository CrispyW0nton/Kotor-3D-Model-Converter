#pragma once

#include <cstddef>

namespace ghostrigger::level {

#ifndef GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& leveltransform_from_dict_line_49_1ea35e51_native();
const NativeFunctionImplementation& walkmeshreference_from_dict_line_77_7fa286f9_native();
const NativeFunctionImplementation& roominstance_from_dict_line_120_da85e907_native();
const NativeFunctionImplementation& moduleinstance_from_dict_line_172_68333948_native();
const NativeFunctionImplementation& blueprintentry_from_dict_line_218_4e37aafd_native();
const NativeFunctionImplementation& texturereference_from_dict_line_255_862fc274_native();
const NativeFunctionImplementation& materialreference_from_dict_line_289_228b1ab3_native();
const NativeFunctionImplementation& kmapserializer_load_line_28_e5a2fa68_native();
const NativeFunctionImplementation& kmapserializer_save_line_40_3982bcf2_native();
const NativeFunctionImplementation& kmapserializer_validate_schema_line_51_2ab5f475_native();
const NativeFunctionImplementation& kmapserializer_migrate_line_75_43020a99_native();
const NativeFunctionImplementation& kmapserializer_from_dict_line_84_6823bdcb_native();
const NativeFunctionImplementation& kmapserializer_to_dict_line_141_8a731e1d_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::level
