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

const NativeFunctionImplementation& packagedmoduleresource_key_line_35_f11e45e7_native();
const NativeFunctionImplementation& moduleinfo_label_line_25_06a18914_native();
const NativeFunctionImplementation& moduleeditorcontroller_project_line_33_3719cfbd_native();
const NativeFunctionImplementation& moduleeditormodel_scene_line_29_c3d7753c_native();
const NativeFunctionImplementation& moduleresourcerecord_key_line_49_42d115cb_native();
const NativeFunctionImplementation& modulereplacementresource_key_line_136_58506ade_native();
const NativeFunctionImplementation& modulearchiveentry_key_line_154_3c786bf1_native();
const NativeFunctionImplementation& walkmeshface_color_line_151_366a94f0_native();
const NativeFunctionImplementation& walkmeshface_normal_line_155_2b51a16b_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_visible_line_753_0e217618_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_key_line_814_e16bcb57_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_overlay_count_line_819_771599f7_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::modulemeshes
