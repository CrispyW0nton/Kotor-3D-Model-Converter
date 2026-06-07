#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_validation {

const char* src_core_validation_viewport_validator_viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._looks_like_ascii_mdl","name":"_looks_like_ascii_mdl","kind":"static_methods","line":58,"end_line":69,"signature":{"args":["raw"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_validation_viewport_validator_viewportvalidator_game_version_line_72_8a0a958f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._game_version","name":"_game_version","kind":"static_methods","line":72,"end_line":75,"signature":{"args":["game"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_validation_viewport_validator_viewportvalidator_to_wxyz_line_245_84c4d9fa_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._to_wxyz","name":"_to_wxyz","kind":"static_methods","line":245,"end_line":253,"signature":{"args":["rotation_xyzw"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_validation_viewport_validator_viewportvalidator_read_grayscale_line_283_29fcf5e8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Validation","python_module":"src.core.validation.viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._read_grayscale","name":"_read_grayscale","kind":"static_methods","line":283,"end_line":292,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/validation/viewport_validator.py", "ViewportValidator._looks_like_ascii_mdl", "static_methods", &src_core_validation_viewport_validator_viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_descriptor_json},
        {"src/core/validation/viewport_validator.py", "ViewportValidator._game_version", "static_methods", &src_core_validation_viewport_validator_viewportvalidator_game_version_line_72_8a0a958f_descriptor_json},
        {"src/core/validation/viewport_validator.py", "ViewportValidator._to_wxyz", "static_methods", &src_core_validation_viewport_validator_viewportvalidator_to_wxyz_line_245_84c4d9fa_descriptor_json},
        {"src/core/validation/viewport_validator.py", "ViewportValidator._read_grayscale", "static_methods", &src_core_validation_viewport_validator_viewportvalidator_read_grayscale_line_283_29fcf5e8_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_validation
