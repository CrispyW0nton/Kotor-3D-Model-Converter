#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_templates {

const char* src_core_templates_twoda_twoda_parse_binary_get_str_line_175_54443ef9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Templates","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA._parse_binary.get_str","name":"get_str","kind":"nested_functions","line":175,"end_line":182,"signature":{"args":["offset"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/templates/twoda.py", "TwoDA._parse_binary.get_str", "nested_functions", &src_core_templates_twoda_twoda_parse_binary_get_str_line_175_54443ef9_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_templates
