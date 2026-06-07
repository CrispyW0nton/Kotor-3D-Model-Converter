#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_export {

const char* src_core_export_gltf_importer_glbreader_from_file_line_140_8725bc1b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLBReader.from_file","name":"from_file","kind":"class_methods","line":140,"end_line":141,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_export_gltf_importer_glbreader_from_bytes_line_144_89250c96_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLBReader.from_bytes","name":"from_bytes","kind":"class_methods","line":144,"end_line":145,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/export/gltf_importer.py", "GLBReader.from_file", "class_methods", &src_core_export_gltf_importer_glbreader_from_file_line_140_8725bc1b_descriptor_json},
        {"src/core/export/gltf_importer.py", "GLBReader.from_bytes", "class_methods", &src_core_export_gltf_importer_glbreader_from_bytes_line_144_89250c96_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_export
