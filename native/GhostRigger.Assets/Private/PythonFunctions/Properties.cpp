#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_assets {

const char* src_core_assets_override_layer_overridelayer_game_dir_line_112_49db4eaa_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Assets","python_module":"src.core.assets.override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.game_dir","name":"game_dir","kind":"properties","line":112,"end_line":113,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_assets_override_layer_overridelayer_override_dir_line_116_d702c23f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Assets","python_module":"src.core.assets.override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.override_dir","name":"override_dir","kind":"properties","line":116,"end_line":117,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_assets_override_layer_overridelayer_is_available_line_120_4fde95ac_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Assets","python_module":"src.core.assets.override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.is_available","name":"is_available","kind":"properties","line":120,"end_line":122,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_assets_override_layer_overridelayer_entry_count_line_125_b6182ba0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Assets","python_module":"src.core.assets.override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.entry_count","name":"entry_count","kind":"properties","line":125,"end_line":127,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/assets/override_layer.py", "OverrideLayer.game_dir", "properties", &src_core_assets_override_layer_overridelayer_game_dir_line_112_49db4eaa_descriptor_json},
        {"src/core/assets/override_layer.py", "OverrideLayer.override_dir", "properties", &src_core_assets_override_layer_overridelayer_override_dir_line_116_d702c23f_descriptor_json},
        {"src/core/assets/override_layer.py", "OverrideLayer.is_available", "properties", &src_core_assets_override_layer_overridelayer_is_available_line_120_4fde95ac_descriptor_json},
        {"src/core/assets/override_layer.py", "OverrideLayer.entry_count", "properties", &src_core_assets_override_layer_overridelayer_entry_count_line_125_b6182ba0_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_assets
