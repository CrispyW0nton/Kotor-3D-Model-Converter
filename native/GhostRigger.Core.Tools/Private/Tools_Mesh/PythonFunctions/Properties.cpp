#include "Tools_Mesh/PythonFunctions/Properties.h"

namespace ghostrigger::core::meshtools {

const NativeFunctionImplementation& meshselectionmode_label_line_27_440b6e12_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_edit_types",
        "src/mesh_tools/mesh_edit_types.py",
        "MeshSelectionMode.label",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshSelectionMode.label","name":"label","callable_type":"properties","line":27,"end_line":28,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        meshselectionmode_label_line_27_440b6e12_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::meshtools
