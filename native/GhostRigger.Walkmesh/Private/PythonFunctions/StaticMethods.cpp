#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_walkmesh {

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_roundtrip_line_568_cd29482e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter.roundtrip","name":"roundtrip","kind":"static_methods","line":568,"end_line":582,"signature":{"args":["overlay"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_compute_adjacency_line_631_816fefe7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._compute_adjacency","name":"_compute_adjacency","kind":"static_methods","line":631,"end_line":662,"signature":{"args":["face_triples"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_pack_line_665_044477c6_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Walkmesh","python_module":"src.core.walkmesh.walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._pack","name":"_pack","kind":"static_methods","line":665,"end_line":709,"signature":{"args":["verts","faces","materials","adjacencies"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshWriter.roundtrip", "static_methods", &src_core_walkmesh_walkmesh_renderer_walkmeshwriter_roundtrip_line_568_cd29482e_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshWriter._compute_adjacency", "static_methods", &src_core_walkmesh_walkmesh_renderer_walkmeshwriter_compute_adjacency_line_631_816fefe7_descriptor_json},
        {"src/core/walkmesh/walkmesh_renderer.py", "WalkmeshWriter._pack", "static_methods", &src_core_walkmesh_walkmesh_renderer_walkmeshwriter_pack_line_665_044477c6_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
