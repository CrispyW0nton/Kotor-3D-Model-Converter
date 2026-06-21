#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::modulemeshes {

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

const NativeFunctionImplementation& aredata_from_bytes_get_line_254_7b32e3fd_native();
const NativeFunctionImplementation& aredata_from_bytes_unpack_color_line_259_f459f580_native();
const NativeFunctionImplementation& gitdata_from_bytes_f_line_359_cd338368_native();
const NativeFunctionImplementation& gitdata_from_bytes_s_line_364_84c169a9_native();
const NativeFunctionImplementation& gitdata_from_bytes_i_line_368_c6c42b3d_native();
const NativeFunctionImplementation& ifodata_from_bytes_s_line_473_22235eff_native();
const NativeFunctionImplementation& ifodata_from_bytes_f_line_479_a5527165_native();
const NativeFunctionImplementation& ifodata_from_bytes_i_line_484_f55d5644_native();
const NativeFunctionImplementation& wokdata_from_pykotor_bwm_vertex_index_line_587_c514930a_native();
const NativeFunctionImplementation& wokdata_from_pykotor_bwm_face_index_line_596_9009dbc5_native();
const NativeFunctionImplementation& wokdata_face_at_point_sign_line_736_af46a9ee_native();
const NativeFunctionImplementation& walkmeshwallgenerator_generate_add_vert_line_859_efac3f70_native();
const NativeFunctionImplementation& kotormodule_from_directory_load_line_958_693f72fb_native();
const NativeFunctionImplementation& moduleloader_load_from_lyt_text_minimalmodule_construct_line_271_22a7169d_native();
const NativeFunctionImplementation& moduleloader_load_from_lyt_text_minimalmodule_summary_line_281_7bca94cc_native();
const NativeFunctionImplementation& walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::modulemeshes
