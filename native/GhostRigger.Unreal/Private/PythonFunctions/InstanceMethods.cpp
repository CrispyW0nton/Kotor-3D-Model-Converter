#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_unreal {

const char* src_unreal_quinn_fbxnode_child_line_58_e1028af9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Unreal","python_module":"src.unreal.quinn","python_file":"src/unreal/quinn.py","qualname":"_FbxNode.child","name":"child","kind":"instance_methods","line":58,"end_line":62,"signature":{"args":["self","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_unreal_quinn_fbxnode_children_named_line_64_07b0592d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Unreal","python_module":"src.unreal.quinn","python_file":"src/unreal/quinn.py","qualname":"_FbxNode.children_named","name":"children_named","kind":"instance_methods","line":64,"end_line":65,"signature":{"args":["self","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/unreal/quinn.py", "_FbxNode.child", "instance_methods", &src_unreal_quinn_fbxnode_child_line_58_e1028af9_descriptor_json},
        {"src/unreal/quinn.py", "_FbxNode.children_named", "instance_methods", &src_unreal_quinn_fbxnode_children_named_line_64_07b0592d_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_unreal
