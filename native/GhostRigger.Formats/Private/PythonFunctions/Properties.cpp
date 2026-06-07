#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_formats {

const char* src_formats_gff_types_locstring_english_line_116_e2fec86f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Formats","python_module":"src.formats.gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.english","name":"english","kind":"properties","line":116,"end_line":117,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/formats/gff_types.py", "LocString.english", "properties", &src_formats_gff_types_locstring_english_line_116_e2fec86f_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_formats
