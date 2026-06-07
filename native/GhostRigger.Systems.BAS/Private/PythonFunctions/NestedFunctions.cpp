#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_systems_bas {

const char* src_systems_bas_attachment_alignment_normalize_bas_transform_values_line_38_bdcb89bd_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Systems.BAS","python_module":"src.systems.bas.attachment_alignment","python_file":"src/systems/bas/attachment_alignment.py","qualname":"normalize_bas_transform.values","name":"values","kind":"nested_functions","line":38,"end_line":46,"signature":{"args":["key","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_systems_bas_model_recipe_normalize_bas_layer_transform_values_line_162_3ef7d12a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Systems.BAS","python_module":"src.systems.bas.model_recipe","python_file":"src/systems/bas/model_recipe.py","qualname":"normalize_bas_layer_transform.values","name":"values","kind":"nested_functions","line":162,"end_line":170,"signature":{"args":["key","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/systems/bas/attachment_alignment.py", "normalize_bas_transform.values", "nested_functions", &src_systems_bas_attachment_alignment_normalize_bas_transform_values_line_38_bdcb89bd_descriptor_json},
        {"src/systems/bas/model_recipe.py", "normalize_bas_layer_transform.values", "nested_functions", &src_systems_bas_model_recipe_normalize_bas_layer_transform_values_line_162_3ef7d12a_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_systems_bas
