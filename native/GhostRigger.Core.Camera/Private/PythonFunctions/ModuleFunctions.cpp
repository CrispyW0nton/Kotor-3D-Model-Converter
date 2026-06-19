#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::camera {

const NativeFunctionImplementation& append_render_manifest_line_24_1e0aa46a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Camera",
        "ghostrigger::core::camera::core::camera::render_manifest",
        "src/core/camera/render_manifest.py",
        "append_render_manifest",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Camera","namespace":"ghostrigger::core::camera::core::camera::render_manifest","python_file":"src/core/camera/render_manifest.py","qualname":"append_render_manifest","name":"append_render_manifest","callable_type":"module_functions","line":24,"end_line":37,"signature":{"args":["output_directory","entry"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        append_render_manifest_line_24_1e0aa46a_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::camera
