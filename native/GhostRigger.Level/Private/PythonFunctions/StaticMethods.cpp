#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_level {

const char* src_core_level_kmap_validator_kmapvalidator_valid_transform_line_123_f2f62e68_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_validator","python_file":"src/core/level/kmap_validator.py","qualname":"KMapValidator._valid_transform","name":"_valid_transform","kind":"static_methods","line":123,"end_line":125,"signature":{"args":["transform"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_level_export_bridge_levelexportbridge_single_export_model_line_106_74e418b1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.level_export_bridge","python_file":"src/core/level/level_export_bridge.py","qualname":"LevelExportBridge._single_export_model","name":"_single_export_model","kind":"static_methods","line":106,"end_line":109,"signature":{"args":["project"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/level/kmap_validator.py", "KMapValidator._valid_transform", "static_methods", &src_core_level_kmap_validator_kmapvalidator_valid_transform_line_123_f2f62e68_descriptor_json},
        {"src/core/level/level_export_bridge.py", "LevelExportBridge._single_export_model", "static_methods", &src_core_level_level_export_bridge_levelexportbridge_single_export_model_line_106_74e418b1_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_level
