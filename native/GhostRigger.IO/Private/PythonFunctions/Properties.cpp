#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_io {

const char* src_io_fbx_fbx_sdk_loader_fbxsdkmodules_available_line_22_df5f76b9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.IO","python_module":"src.io.fbx.fbx_sdk_loader","python_file":"src/io/fbx/fbx_sdk_loader.py","qualname":"FbxSdkModules.available","name":"available","kind":"properties","line":22,"end_line":23,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/io/fbx/fbx_sdk_loader.py", "FbxSdkModules.available", "properties", &src_io_fbx_fbx_sdk_loader_fbxsdkmodules_available_line_22_df5f76b9_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_io
