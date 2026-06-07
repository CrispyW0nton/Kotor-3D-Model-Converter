#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::renderer::d3d12 {

const NativeFunctionImplementation& hardwarediagnostics_from_dict_line_56_a66bccdf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Renderer.D3D12",
        "ghostrigger::renderer::d3d12::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "HardwareDiagnostics.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Renderer.D3D12","namespace":"ghostrigger::renderer::d3d12::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"HardwareDiagnostics.from_dict","name":"from_dict","callable_type":"class_methods","line":56,"end_line":71,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        hardwarediagnostics_from_dict_line_56_a66bccdf_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::renderer::d3d12
