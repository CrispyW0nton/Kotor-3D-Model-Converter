#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors {

const char* src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.position","name":"position","kind":"properties","line":54,"end_line":55,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.rotation","name":"rotation","kind":"properties","line":62,"end_line":63,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/scene/scene_object.py", "PivotData.position", "properties", &src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json},
        {"src/core/scene/scene_object.py", "PivotData.rotation", "properties", &src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
