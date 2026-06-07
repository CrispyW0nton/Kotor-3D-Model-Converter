#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_walkmesh {

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._extract_geometry._add_vert","name":"_add_vert","kind":"nested_functions","line":607,"end_line":613,"signature":{"args":["v"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshWriter._extract_geometry._add_vert", "nested_functions", &src_core_walkmesh_walkmesh_renderer_walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
