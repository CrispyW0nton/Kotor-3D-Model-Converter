#pragma once

#include <cstddef>

namespace ghostrigger::tools::modulemeshes {

#ifndef GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

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
const NativeFunctionImplementation& lytlayout_from_text_line_75_b9b667dc_native();
const NativeFunctionImplementation& lytlayout_from_file_line_144_17b82126_native();
const NativeFunctionImplementation& visdata_from_text_line_182_25411b79_native();
const NativeFunctionImplementation& visdata_from_file_line_199_e4a72a20_native();
const NativeFunctionImplementation& aredata_from_bytes_line_249_49ea9dec_native();
const NativeFunctionImplementation& gitdata_from_bytes_line_353_69675c0d_native();
const NativeFunctionImplementation& ifodata_from_bytes_line_467_8b750a00_native();
const NativeFunctionImplementation& wokdata_from_bytes_line_555_79d73e9e_native();
const NativeFunctionImplementation& wokdata_from_pykotor_bwm_line_573_0083a2f7_native();
const NativeFunctionImplementation& wokdata_from_file_line_618_88ca04bf_native();
const NativeFunctionImplementation& kotormodule_from_directory_line_939_586f7036_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::modulemeshes
