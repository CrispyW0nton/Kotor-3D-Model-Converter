#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_schemas_init_basemodel_model_validate_line_23_d78d3b93_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.schemas.__init__","python_file":"src/kotormcp/schemas/__init__.py","qualname":"BaseModel.model_validate","name":"model_validate","kind":"class_methods","line":23,"end_line":31,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/schemas/__init__.py", "BaseModel.model_validate", "class_methods", &src_kotormcp_schemas_init_basemodel_model_validate_line_23_d78d3b93_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
