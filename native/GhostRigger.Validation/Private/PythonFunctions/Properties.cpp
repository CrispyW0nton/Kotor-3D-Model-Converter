#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_validation {

const char* src_core_validation_animation_block_validator_rawanimationfootprintreport_node_names_line_108_8ae23bc4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.animation_block_validator","python_file":"src/core/validation/animation_block_validator.py","qualname":"RawAnimationFootprintReport.node_names","name":"node_names","kind":"properties","line":108,"end_line":109,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_validation_validation_bus_validationreport_has_blocking_line_85_2f48161f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.has_blocking","name":"has_blocking","kind":"properties","line":85,"end_line":86,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_validation_validation_bus_validationreport_has_errors_line_89_1b4a9e00_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.has_errors","name":"has_errors","kind":"properties","line":89,"end_line":90,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_validation_validation_bus_validationreport_blocking_issues_line_93_dd1bb43c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.blocking_issues","name":"blocking_issues","kind":"properties","line":93,"end_line":94,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/validation/animation_block_validator.py", "RawAnimationFootprintReport.node_names", "properties", &src_core_validation_animation_block_validator_rawanimationfootprintreport_node_names_line_108_8ae23bc4_descriptor_json},
        {"src/core/validation/validation_bus.py", "ValidationReport.has_blocking", "properties", &src_core_validation_validation_bus_validationreport_has_blocking_line_85_2f48161f_descriptor_json},
        {"src/core/validation/validation_bus.py", "ValidationReport.has_errors", "properties", &src_core_validation_validation_bus_validationreport_has_errors_line_89_1b4a9e00_descriptor_json},
        {"src/core/validation/validation_bus.py", "ValidationReport.blocking_issues", "properties", &src_core_validation_validation_bus_validationreport_blocking_issues_line_93_dd1bb43c_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_validation
