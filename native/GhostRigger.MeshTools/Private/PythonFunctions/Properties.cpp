#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_meshtools {

const char* src_mesh_tools_mesh_edit_types_meshselectionmode_label_line_27_440b6e12_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshSelectionMode.label","name":"label","kind":"properties","line":27,"end_line":28,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/mesh_tools/mesh_edit_types.py", "MeshSelectionMode.label", "properties", &src_mesh_tools_mesh_edit_types_meshselectionmode_label_line_27_440b6e12_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_meshtools
