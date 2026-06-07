#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_validation {

const char* src_core_validation_animation_block_validator_validate_raw_animation_footprint_walk_line_148_d39479ce_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.animation_block_validator","python_file":"src/core/validation/animation_block_validator.py","qualname":"validate_raw_animation_footprint.walk","name":"walk","kind":"nested_functions","line":148,"end_line":228,"signature":{"args":["node_rel"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_validation_validation_bus_validationbus_subscribe_unsubscribe_line_158_b8f03986_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationBus.subscribe.unsubscribe","name":"unsubscribe","kind":"nested_functions","line":158,"end_line":162,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/validation/animation_block_validator.py", "validate_raw_animation_footprint.walk", "nested_functions", &src_core_validation_animation_block_validator_validate_raw_animation_footprint_walk_line_148_d39479ce_descriptor_json},
        {"src/core/validation/validation_bus.py", "ValidationBus.subscribe.unsubscribe", "nested_functions", &src_core_validation_validation_bus_validationbus_subscribe_unsubscribe_line_158_b8f03986_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_validation
