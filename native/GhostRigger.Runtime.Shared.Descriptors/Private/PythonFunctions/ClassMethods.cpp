#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors {

const char* src_core_project_resource_address_resourceaddress_from_dict_line_87_734cf9ce_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.project.resource_address","python_file":"src/core/project/resource_address.py","qualname":"ResourceAddress.from_dict","name":"from_dict","kind":"class_methods","line":87,"end_line":103,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_scene_scene_object_transform_from_dict_line_35_68aeedb9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"Transform.from_dict","name":"from_dict","kind":"class_methods","line":35,"end_line":41,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_scene_scene_object_pivotdata_from_dict_line_88_6fd6a9f3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.scene.scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.from_dict","name":"from_dict","kind":"class_methods","line":88,"end_line":102,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_scene_scene_object_instance_sceneobjectinstance_from_dict_line_49_531c3383_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.scene.scene_object_instance","python_file":"src/core/scene/scene_object_instance.py","qualname":"SceneObjectInstance.from_dict","name":"from_dict","kind":"class_methods","line":49,"end_line":63,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/project/resource_address.py", "ResourceAddress.from_dict", "class_methods", &src_core_project_resource_address_resourceaddress_from_dict_line_87_734cf9ce_descriptor_json},
        {"src/core/scene/scene_object.py", "Transform.from_dict", "class_methods", &src_core_scene_scene_object_transform_from_dict_line_35_68aeedb9_descriptor_json},
        {"src/core/scene/scene_object.py", "PivotData.from_dict", "class_methods", &src_core_scene_scene_object_pivotdata_from_dict_line_88_6fd6a9f3_descriptor_json},
        {"src/core/scene/scene_object_instance.py", "SceneObjectInstance.from_dict", "class_methods", &src_core_scene_scene_object_instance_sceneobjectinstance_from_dict_line_49_531c3383_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
