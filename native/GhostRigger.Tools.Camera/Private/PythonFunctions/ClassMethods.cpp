#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_camera {

const char* src_core_camera_camera_model_ghostriggercamera_from_object_line_63_00a75f63_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Camera","python_module":"src.core.camera.camera_model","python_file":"src/core/camera/camera_model.py","qualname":"GhostRiggerCamera.from_object","name":"from_object","kind":"class_methods","line":63,"end_line":80,"signature":{"args":["cls","obj"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_camera_camera_model_ghostriggercamera_from_dict_line_83_1d2e8091_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Camera","python_module":"src.core.camera.camera_model","python_file":"src/core/camera/camera_model.py","qualname":"GhostRiggerCamera.from_dict","name":"from_dict","kind":"class_methods","line":83,"end_line":97,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_camera_camera_render_settings_rendersettings_from_dict_line_41_2f47dc1e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Camera","python_module":"src.core.camera.camera_render_settings","python_file":"src/core/camera/camera_render_settings.py","qualname":"RenderSettings.from_dict","name":"from_dict","kind":"class_methods","line":41,"end_line":45,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/camera/camera_model.py", "GhostRiggerCamera.from_object", "class_methods", &src_core_camera_camera_model_ghostriggercamera_from_object_line_63_00a75f63_descriptor_json},
        {"src/core/camera/camera_model.py", "GhostRiggerCamera.from_dict", "class_methods", &src_core_camera_camera_model_ghostriggercamera_from_dict_line_83_1d2e8091_descriptor_json},
        {"src/core/camera/camera_render_settings.py", "RenderSettings.from_dict", "class_methods", &src_core_camera_camera_render_settings_rendersettings_from_dict_line_41_2f47dc1e_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_camera
