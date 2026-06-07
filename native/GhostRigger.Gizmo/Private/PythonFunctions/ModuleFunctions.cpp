#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gizmo {

const char* src_core_gizmo_gizmo_draw_data_rgba255_to_float_line_38_22b0952d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Gizmo","python_module":"src.core.gizmo.gizmo_draw_data","python_file":"src/core/gizmo/gizmo_draw_data.py","qualname":"rgba255_to_float","name":"rgba255_to_float","kind":"module_functions","line":38,"end_line":46,"signature":{"args":["color"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/gizmo/gizmo_draw_data.py", "rgba255_to_float", "module_functions", &src_core_gizmo_gizmo_draw_data_rgba255_to_float_line_38_22b0952d_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gizmo
