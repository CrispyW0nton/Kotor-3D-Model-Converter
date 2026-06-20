#pragma once

#include <cstddef>

namespace ghostrigger::core::ipc {

#ifndef GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ipc_call_line_40_ac90d3de_native();
const NativeFunctionImplementation& marshal_to_gui_thread_line_85_eefdf9c9_native();
const NativeFunctionImplementation& ipc_call_async_line_99_4660fcf5_native();
const NativeFunctionImplementation& notify_blueprint_saved_line_126_8c8df0fa_native();
const NativeFunctionImplementation& refresh_gmodular_viewport_line_141_253985ae_native();
const NativeFunctionImplementation& show_ghostrigger_panel_line_155_2f579067_native();
const NativeFunctionImplementation& open_ghostrigger_tool_line_165_bcc51ebf_native();
const NativeFunctionImplementation& run_ghostrigger_viewport_command_line_175_dd1028a5_native();
const NativeFunctionImplementation& get_ghostrigger_state_line_187_394ecd14_native();
const NativeFunctionImplementation& set_ghostrigger_appearance_line_192_97c61399_native();
const NativeFunctionImplementation& run_ghostrigger_animation_command_line_202_1ae1832b_native();
const NativeFunctionImplementation& search_ghostrigger_library_line_224_33f2c865_native();
const NativeFunctionImplementation& select_ghostrigger_library_asset_line_243_223f447c_native();
const NativeFunctionImplementation& search_ghostrigger_resources_line_264_3fdb730a_native();
const NativeFunctionImplementation& select_ghostrigger_resource_line_280_4ceba30f_native();
const NativeFunctionImplementation& new_ghostrigger_scene_line_299_d0f6d152_native();
const NativeFunctionImplementation& open_ghostrigger_scene_line_309_edf51d3c_native();
const NativeFunctionImplementation& save_ghostrigger_scene_line_319_4741e83c_native();
const NativeFunctionImplementation& create_ghostrigger_scene_camera_line_329_1ba6a7af_native();
const NativeFunctionImplementation& create_ghostrigger_scene_light_line_339_03dc3d63_native();
const NativeFunctionImplementation& select_ghostrigger_scene_object_line_349_13fb2547_native();
const NativeFunctionImplementation& set_ghostrigger_scene_object_visibility_line_359_9b460b02_native();
const NativeFunctionImplementation& run_ghostrigger_scene_object_command_line_374_1c524389_native();
const NativeFunctionImplementation& set_ghostrigger_scene_object_properties_line_388_9921c09a_native();
const NativeFunctionImplementation& select_ghostrigger_module_mesh_line_401_9d8fad27_native();
const NativeFunctionImplementation& set_ghostrigger_renderer_backend_line_411_3cbfb425_native();
const NativeFunctionImplementation& set_ghostrigger_dummy_helpers_line_424_07b929e8_native();
const NativeFunctionImplementation& set_ghostrigger_light_helpers_line_434_55a013bf_native();
const NativeFunctionImplementation& select_ghostrigger_helper_line_447_383b7092_native();
const NativeFunctionImplementation& capture_ghostrigger_viewport_line_457_7b4c3cf5_native();
const NativeFunctionImplementation& open_script_in_scripter_line_467_1d360a0f_native();
const NativeFunctionImplementation& open_dlg_in_scripter_line_481_e4fd79c3_native();
const NativeFunctionImplementation& ping_program_line_495_d03614ea_native();
const NativeFunctionImplementation& ping_all_line_514_d2ea7cd2_native();
const NativeFunctionImplementation& log_result_line_526_623eb031_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::ipc
