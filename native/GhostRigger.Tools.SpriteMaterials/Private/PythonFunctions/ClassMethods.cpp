#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::tools::spritematerials {

const NativeFunctionImplementation& materialtrack_deserialize_line_51_ed9b85b8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.SpriteMaterials",
        "ghostrigger::tools::spritematerials::sequence::tracks::material_track",
        "src/sequence/tracks/material_track.py",
        "MaterialTrack.deserialize",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.SpriteMaterials","namespace":"ghostrigger::tools::spritematerials::sequence::tracks::material_track","python_file":"src/sequence/tracks/material_track.py","qualname":"MaterialTrack.deserialize","name":"deserialize","callable_type":"class_methods","line":51,"end_line":66,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        materialtrack_deserialize_line_51_ed9b85b8_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::spritematerials
