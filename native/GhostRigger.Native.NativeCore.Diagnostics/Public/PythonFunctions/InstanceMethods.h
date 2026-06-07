#pragma once

#include <cstddef>

namespace ghostrigger::native::nativecore::diagnostics {

#ifndef GHOSTRIGGER_NATIVE_NATIVECORE_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_NATIVE_NATIVECORE_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_NATIVE_NATIVECORE_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& validationissue_str_line_80_60e97a2e_native();
const NativeFunctionImplementation& validationservice_construct_line_169_9a802500_native();
const NativeFunctionImplementation& validationservice_validate_line_183_932d2b00_native();
const NativeFunctionImplementation& validationservice_add_line_231_53afb934_native();
const NativeFunctionImplementation& validationservice_err_line_244_d0f8fc23_native();
const NativeFunctionImplementation& validationservice_warn_line_247_cdc72eb5_native();
const NativeFunctionImplementation& validationservice_info_line_250_8dd95131_native();
const NativeFunctionImplementation& validationservice_check_scene_not_empty_line_255_e581716d_native();
const NativeFunctionImplementation& validationservice_check_k1_k2_mismatch_line_273_77cc33d4_native();
const NativeFunctionImplementation& validationservice_check_supermodel_consistency_line_285_754d90fd_native();
const NativeFunctionImplementation& validationservice_get_node_map_line_311_7d6ec50e_native();
const NativeFunctionImplementation& validationservice_check_hooks_line_321_55897384_native();
const NativeFunctionImplementation& validationservice_check_facial_bones_line_340_bc73e4db_native();
const NativeFunctionImplementation& validationservice_check_skin_weights_line_351_bfed3096_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::native::nativecore::diagnostics
