#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::tools::camera {

const NativeFunctionImplementation& append_render_manifest_line_24_1e0aa46a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Camera",
        "ghostrigger::tools::camera::core::camera::render_manifest",
        "src/core/camera/render_manifest.py",
        "append_render_manifest",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Camera","namespace":"ghostrigger::tools::camera::core::camera::render_manifest","python_file":"src/core/camera/render_manifest.py","qualname":"append_render_manifest","name":"append_render_manifest","callable_type":"module_functions","line":24,"end_line":37,"signature":{"args":["output_directory","entry"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& getattr_line_19_bd15a5bb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Camera",
        "ghostrigger::tools::camera::gui::camera::init",
        "src/gui/camera/__init__.py",
        "__getattr__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Camera","namespace":"ghostrigger::tools::camera::gui::camera::init","python_file":"src/gui/camera/__init__.py","qualname":"__getattr__","name":"__getattr__","callable_type":"module_functions","line":19,"end_line":25,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& dir_line_28_8f929c2b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Camera",
        "ghostrigger::tools::camera::gui::camera::init",
        "src/gui/camera/__init__.py",
        "__dir__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Camera","namespace":"ghostrigger::tools::camera::gui::camera::init","python_file":"src/gui/camera/__init__.py","qualname":"__dir__","name":"__dir__","callable_type":"module_functions","line":28,"end_line":29,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        append_render_manifest_line_24_1e0aa46a_native(),
        getattr_line_19_bd15a5bb_native(),
        dir_line_28_8f929c2b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::camera
