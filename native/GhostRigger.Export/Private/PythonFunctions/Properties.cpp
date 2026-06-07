#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_export {

const char* src_core_export_export_job_exportjobresult_succeeded_line_104_a5b01fae_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Export","python_module":"src.core.export.export_job","python_file":"src/core/export/export_job.py","qualname":"ExportJobResult.succeeded","name":"succeeded","kind":"properties","line":104,"end_line":105,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/export/export_job.py", "ExportJobResult.succeeded", "properties", &src_core_export_export_job_exportjobresult_succeeded_line_104_a5b01fae_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_export
