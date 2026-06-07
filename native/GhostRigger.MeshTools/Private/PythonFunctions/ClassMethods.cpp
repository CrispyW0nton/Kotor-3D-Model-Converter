#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_meshtools {

const char* src_mesh_tools_mesh_edit_types_meshoperationresult_ok_line_42_faf3927d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshOperationResult.ok","name":"ok","kind":"class_methods","line":42,"end_line":58,"signature":{"args":["cls","message","changed_mesh_ids","selection_changed","topology_changed","warnings"],"positional_count":2,"keyword_only_count":4,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_mesh_tools_mesh_edit_types_meshoperationresult_fail_line_61_15657c24_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshOperationResult.fail","name":"fail","kind":"class_methods","line":61,"end_line":68,"signature":{"args":["cls","message","errors","warnings"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_mesh_tools_mesh_topology_meshtopology_build_from_mesh_line_64_8c7ee68b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_topology","python_file":"src/mesh_tools/mesh_topology.py","qualname":"MeshTopology.build_from_mesh","name":"build_from_mesh","kind":"class_methods","line":64,"end_line":69,"signature":{"args":["cls","mesh"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_mesh_tools_mesh_topology_meshtopology_rebuild_after_edit_line_72_26c2a3ab_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_topology","python_file":"src/mesh_tools/mesh_topology.py","qualname":"MeshTopology.rebuild_after_edit","name":"rebuild_after_edit","kind":"class_methods","line":72,"end_line":73,"signature":{"args":["cls","mesh"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/mesh_tools/mesh_edit_types.py", "MeshOperationResult.ok", "class_methods", &src_mesh_tools_mesh_edit_types_meshoperationresult_ok_line_42_faf3927d_descriptor_json},
        {"src/mesh_tools/mesh_edit_types.py", "MeshOperationResult.fail", "class_methods", &src_mesh_tools_mesh_edit_types_meshoperationresult_fail_line_61_15657c24_descriptor_json},
        {"src/mesh_tools/mesh_topology.py", "MeshTopology.build_from_mesh", "class_methods", &src_mesh_tools_mesh_topology_meshtopology_build_from_mesh_line_64_8c7ee68b_descriptor_json},
        {"src/mesh_tools/mesh_topology.py", "MeshTopology.rebuild_after_edit", "class_methods", &src_mesh_tools_mesh_topology_meshtopology_rebuild_after_edit_line_72_26c2a3ab_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_meshtools
