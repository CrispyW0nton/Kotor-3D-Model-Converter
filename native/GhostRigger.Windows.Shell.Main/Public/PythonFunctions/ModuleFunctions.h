#pragma once

#include <cstddef>

namespace ghostrigger::windows::shell::main {

#ifndef GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& make_package_line_116_3b225a79_native();
const NativeFunctionImplementation& register_alias_line_123_cfe75bc1_native();
const NativeFunctionImplementation& register_group_line_133_69d31992_native();
const NativeFunctionImplementation& run_qt_application_line_17_22c2bb63_native();
const NativeFunctionImplementation& bounds_from_points_line_12_0f5b3342_native();
const NativeFunctionImplementation& bounds_center_line_28_529ac354_native();
const NativeFunctionImplementation& bounds_overlap_xy_line_35_0875c0d3_native();
const NativeFunctionImplementation& walkmesh_reference_bounds_line_43_cb8ce1d1_native();
const NativeFunctionImplementation& walkmesh_overlay_offset_for_model_line_70_a715a3f3_native();
const NativeFunctionImplementation& walkmesh_overlay_node_from_wok_line_99_9a392cbb_native();
const NativeFunctionImplementation& prebuild_gpu_mesh_data_for_model_line_125_ad6175f6_native();
const NativeFunctionImplementation& wgpu_backend_type_line_25_b08cfaf1_native();
const NativeFunctionImplementation& wgpu_backend_restart_required_line_28_f31e2dd1_native();
const NativeFunctionImplementation& primary_screen_available_geometry_line_36_e708b4ac_native();
const NativeFunctionImplementation& qt_object_alive_line_45_c0bd40f8_native();
const NativeFunctionImplementation& lighten_hex_line_15_c934fdb4_native();
const NativeFunctionImplementation& darken_hex_line_20_90dbbcf7_native();
const NativeFunctionImplementation& surface_fill_line_25_99123150_native();
const NativeFunctionImplementation& palette_hex_line_38_0315949c_native();
const NativeFunctionImplementation& native_splash_palette_colors_line_41_783cc396_native();
const NativeFunctionImplementation& index_game_libraries_sync_line_19_429b5955_native();
const NativeFunctionImplementation& scan_library_rows_sync_line_37_e39110c2_native();
const NativeFunctionImplementation& read_settings_file_line_40_73ac53bf_native();
const NativeFunctionImplementation& write_settings_file_line_47_78408892_native();
const NativeFunctionImplementation& build_prelaunch_library_input_line_52_6d0bd1d7_native();
const NativeFunctionImplementation& collect_prewindow_startup_diagnostics_line_121_7f35bd93_native();
const NativeFunctionImplementation& load_resource_model_from_game_resources_line_122_42a051a5_native();
const NativeFunctionImplementation& lighten_hex_line_15_805afa9c_native();
const NativeFunctionImplementation& darken_hex_line_22_1be83d41_native();
const NativeFunctionImplementation& surface_fill_line_29_c3e65dcb_native();
const NativeFunctionImplementation& index_game_libraries_sync_line_194_8f2842f7_native();
const NativeFunctionImplementation& scan_library_rows_sync_line_198_49b27f21_native();
const NativeFunctionImplementation& build_prelaunch_library_input_line_203_1a4d4d40_native();
const NativeFunctionImplementation& run_line_1039_f822e3ed_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::windows::shell::main
