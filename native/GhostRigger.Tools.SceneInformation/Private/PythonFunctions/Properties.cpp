#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_tools_sceneinformation {

const char* src_core_scene_axis_mode_axismode_label_line_25_7f940ea5_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SceneInformation","python_module":"src.core.scene.axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.label","name":"label","kind":"properties","line":25,"end_line":26,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_scene_kmax_scene_kmaxscene_display_name_line_43_4c4f5179_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SceneInformation","python_module":"src.core.scene.kmax_scene","python_file":"src/core/scene/kmax_scene.py","qualname":"KMaxScene.display_name","name":"display_name","kind":"properties","line":43,"end_line":46,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_scene_module_scene_import_moduleroomplacement_group_id_line_26_2739f71f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SceneInformation","python_module":"src.core.scene.module_scene_import","python_file":"src/core/scene/module_scene_import.py","qualname":"ModuleRoomPlacement.group_id","name":"group_id","kind":"properties","line":26,"end_line":27,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SceneInformation","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.position","name":"position","kind":"properties","line":54,"end_line":55,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SceneInformation","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.rotation","name":"rotation","kind":"properties","line":62,"end_line":63,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/scene/axis_mode.py", "AxisMode.label", "properties", &src_core_scene_axis_mode_axismode_label_line_25_7f940ea5_descriptor_json},
        {"src/core/scene/kmax_scene.py", "KMaxScene.display_name", "properties", &src_core_scene_kmax_scene_kmaxscene_display_name_line_43_4c4f5179_descriptor_json},
        {"src/core/scene/module_scene_import.py", "ModuleRoomPlacement.group_id", "properties", &src_core_scene_module_scene_import_moduleroomplacement_group_id_line_26_2739f71f_descriptor_json},
        {"src/core/scene/scene_object.py", "PivotData.position", "properties", &src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json},
        {"src/core/scene/scene_object.py", "PivotData.rotation", "properties", &src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_sceneinformation
