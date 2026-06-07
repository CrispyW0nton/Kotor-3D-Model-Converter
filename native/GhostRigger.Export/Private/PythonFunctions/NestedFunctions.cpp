#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_export {

const char* src_core_export_gltf_importer_gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLTFImporter._process_pygltflib._acc","name":"_acc","kind":"nested_functions","line":518,"end_line":542,"signature":{"args":["idx"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_export_gltf_importer_gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLTFImporter._import_builtin_bytes._acc","name":"_acc","kind":"nested_functions","line":726,"end_line":727,"signature":{"args":["idx"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_export_gltf_importer_candidate_blender_executables_add_line_1087_320d6829_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_candidate_blender_executables.add","name":"add","kind":"nested_functions","line":1087,"end_line":1096,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/export/gltf_importer.py", "GLTFImporter._process_pygltflib._acc", "nested_functions", &src_core_export_gltf_importer_gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_descriptor_json},
        {"src/core/export/gltf_importer.py", "GLTFImporter._import_builtin_bytes._acc", "nested_functions", &src_core_export_gltf_importer_gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_descriptor_json},
        {"src/core/export/gltf_importer.py", "_candidate_blender_executables.add", "nested_functions", &src_core_export_gltf_importer_candidate_blender_executables_add_line_1087_320d6829_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_export
