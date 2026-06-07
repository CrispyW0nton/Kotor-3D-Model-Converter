#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_templates {

const char* src_core_templates_twoda_twodarow_index_line_40_53831d48_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Templates","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDARow.index","name":"index","kind":"properties","line":40,"end_line":41,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/templates/twoda.py", "TwoDARow.index", "properties", &src_core_templates_twoda_twodarow_index_line_40_53831d48_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_templates
