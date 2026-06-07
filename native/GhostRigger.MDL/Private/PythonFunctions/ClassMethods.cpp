#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_mdl {

const char* src_core_mdl_mdl_parser_mdlbinaryparser_from_files_line_74_5167f1ce_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MDL","python_module":"src.core.mdl.mdl_parser","python_file":"src/core/mdl/mdl_parser.py","qualname":"MDLBinaryParser.from_files","name":"from_files","kind":"class_methods","line":74,"end_line":82,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_mdl_mdl_parser_mdlbinaryparser_parse_files_line_85_cd15af6e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MDL","python_module":"src.core.mdl.mdl_parser","python_file":"src/core/mdl/mdl_parser.py","qualname":"MDLBinaryParser.parse_files","name":"parse_files","kind":"class_methods","line":85,"end_line":87,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_mdl_mdl_writer_mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MDL","python_module":"src.core.mdl.mdl_writer","python_file":"src/core/mdl/mdl_writer.py","qualname":"MDLBinaryWriter._ensure_export_orientation_controller","name":"_ensure_export_orientation_controller","kind":"class_methods","line":1723,"end_line":1736,"signature":{"args":["cls","node","times"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/mdl/mdl_parser.py", "MDLBinaryParser.from_files", "class_methods", &src_core_mdl_mdl_parser_mdlbinaryparser_from_files_line_74_5167f1ce_descriptor_json},
        {"src/core/mdl/mdl_parser.py", "MDLBinaryParser.parse_files", "class_methods", &src_core_mdl_mdl_parser_mdlbinaryparser_parse_files_line_85_cd15af6e_descriptor_json},
        {"src/core/mdl/mdl_writer.py", "MDLBinaryWriter._ensure_export_orientation_controller", "class_methods", &src_core_mdl_mdl_writer_mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_mdl
