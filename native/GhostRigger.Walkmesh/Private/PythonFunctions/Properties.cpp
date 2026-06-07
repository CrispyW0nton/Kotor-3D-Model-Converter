#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_walkmesh {

const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_color_line_151_366a94f0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshFace.color","name":"color","kind":"properties","line":151,"end_line":152,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_normal_line_155_2b51a16b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshFace.normal","name":"normal","kind":"properties","line":155,"end_line":165,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_visible_line_753_0e217618_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.visible","name":"visible","kind":"properties","line":753,"end_line":755,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_key_line_814_e16bcb57_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.key","name":"key","kind":"properties","line":814,"end_line":816,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_overlay_count_line_819_771599f7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.overlay_count","name":"overlay_count","kind":"properties","line":819,"end_line":821,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshFace.color", "properties", &src_core_walkmesh_walkmesh_renderer_walkmeshface_color_line_151_366a94f0_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshFace.normal", "properties", &src_core_walkmesh_walkmesh_renderer_walkmeshface_normal_line_155_2b51a16b_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshToggleController.visible", "properties", &src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_visible_line_753_0e217618_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshToggleController.key", "properties", &src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_key_line_814_e16bcb57_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshToggleController.overlay_count", "properties", &src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_overlay_count_line_819_771599f7_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
