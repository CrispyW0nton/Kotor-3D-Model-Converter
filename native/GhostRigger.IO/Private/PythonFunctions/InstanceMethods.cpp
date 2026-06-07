#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_io {

const char* src_io_fbx_fbx_scene_adapter_fbximportsummary_log_line_line_23_d3f43f45_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.IO","python_module":"src.io.fbx.fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"FbxImportSummary.log_line","name":"log_line","kind":"instance_methods","line":23,"end_line":27,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_io_fbx_fbx_scene_adapter_fbxexportsummary_log_line_line_39_848f749e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.IO","python_module":"src.io.fbx.fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"FbxExportSummary.log_line","name":"log_line","kind":"instance_methods","line":39,"end_line":43,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/io/fbx/fbx_scene_adapter.py", "FbxImportSummary.log_line", "instance_methods", &src_io_fbx_fbx_scene_adapter_fbximportsummary_log_line_line_23_d3f43f45_descriptor_json},
        {"src/io/fbx/fbx_scene_adapter.py", "FbxExportSummary.log_line", "instance_methods", &src_io_fbx_fbx_scene_adapter_fbxexportsummary_log_line_line_39_848f749e_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_io
