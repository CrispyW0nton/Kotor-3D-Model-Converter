#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::viewports {

#ifndef GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& viewportdraginteractionsmixin_apply_gimbal_drag_axis_delta_line_756_94b2cdad_native();
const NativeFunctionImplementation& viewportdraginteractionsmixin_draw_mesh_subobject_selection_point_line_1114_5dd0970e_native();
const NativeFunctionImplementation& viewportdraginteractionsmixin_draw_mesh_subobject_selection_draw_edge_line_1122_3690c91e_native();
const NativeFunctionImplementation& viewportpickinghovermixin_apply_mesh_subobject_hit_update_set_line_305_68f1ed55_native();
const NativeFunctionImplementation& viewportpickinghovermixin_update_mesh_hover_clear_hover_line_1050_777a470e_native();
const NativeFunctionImplementation& viewportpickinghovermixin_update_mesh_hover_set_hover_line_1068_33a26edb_native();
const NativeFunctionImplementation& viewportrenderingpipelinemixin_start_deferred_txi_metadata_load_line_66_183ebc96_native();
const NativeFunctionImplementation& viewportrenderingpipelinemixin_render_gpu_frame_continue_uploads_line_464_823a5599_native();
const NativeFunctionImplementation& viewportrenderingpipelinemixin_renderer_statistics_lines_number_line_619_e7062561_native();
const NativeFunctionImplementation& viewportresourcecachemixin_prewarm_textures_load_line_100_10beff55_native();
const NativeFunctionImplementation& viewporttransformcameramixin_euler_degrees_to_quat_axis_quat_line_61_0ee9c5d6_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::viewports
