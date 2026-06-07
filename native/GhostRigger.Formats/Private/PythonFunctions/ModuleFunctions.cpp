#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_formats {

const char* src_formats_gff_reader_read_gff_line_271_ba45cf01_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Formats","python_module":"src.formats.gff_reader","python_file":"src/formats/gff_reader.py","qualname":"read_gff","name":"read_gff","kind":"module_functions","line":271,"end_line":273,"signature":{"args":["data"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_formats_gff_writer_write_gff_line_306_9e3facfa_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Formats","python_module":"src.formats.gff_writer","python_file":"src/formats/gff_writer.py","qualname":"write_gff","name":"write_gff","kind":"module_functions","line":306,"end_line":308,"signature":{"args":["gff"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/formats/gff_reader.py", "read_gff", "module_functions", &src_formats_gff_reader_read_gff_line_271_ba45cf01_descriptor_json},
        {"src/formats/gff_writer.py", "write_gff", "module_functions", &src_formats_gff_writer_write_gff_line_306_9e3facfa_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_formats
