#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_formats {

const char* src_formats_gff_writer_gffwriter_serialize_collect_line_59_1e5f42ee_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Formats","python_module":"src.formats.gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter.serialize._collect","name":"_collect","kind":"nested_functions","line":59,"end_line":75,"signature":{"args":["s"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/formats/gff_writer.py", "GffWriter.serialize._collect", "nested_functions", &src_formats_gff_writer_gffwriter_serialize_collect_line_59_1e5f42ee_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_formats
