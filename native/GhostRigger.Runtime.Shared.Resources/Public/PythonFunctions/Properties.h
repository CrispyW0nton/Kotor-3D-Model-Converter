#pragma once

#include <cstddef>

namespace ghostrigger::runtime::shared::resources {

#ifndef GHOSTRIGGER_RUNTIME_SHARED_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RUNTIME_SHARED_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RUNTIME_SHARED_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& overridelayer_game_dir_line_112_49db4eaa_native();
const NativeFunctionImplementation& overridelayer_override_dir_line_116_d702c23f_native();
const NativeFunctionImplementation& overridelayer_is_available_line_120_4fde95ac_native();
const NativeFunctionImplementation& overridelayer_entry_count_line_125_b6182ba0_native();
const NativeFunctionImplementation& gameresourcerecord_resref_line_116_3d616c56_native();
const NativeFunctionImplementation& gameresourcerecord_restype_line_120_1d46f82f_native();
const NativeFunctionImplementation& gameresourcerecord_layer_line_124_3bab406c_native();
const NativeFunctionImplementation& gameresourcerecord_key_line_128_f409ca4e_native();
const NativeFunctionImplementation& gameresourceresult_address_line_147_0e30bfb9_native();
const NativeFunctionImplementation& resourceentry_is_model_line_148_43c8a66b_native();
const NativeFunctionImplementation& resourceentry_is_texture_line_158_fe34306f_native();
const NativeFunctionImplementation& resourceentry_ext_line_176_0604481f_native();
const NativeFunctionImplementation& resourceentry_filename_line_183_c3d15313_native();
const NativeFunctionImplementation& modellibraryentry_display_label_line_564_bd018b8d_native();
const NativeFunctionImplementation& modellibraryentry_display_label_rich_line_572_ec474d1b_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime::shared::resources
