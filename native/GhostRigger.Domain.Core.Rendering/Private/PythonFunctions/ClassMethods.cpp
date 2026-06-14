#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::domain::core::rendering {

const NativeFunctionImplementation& hardwarediagnostics_from_dict_line_56_a66bccdf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Rendering",
        "ghostrigger::domain::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "HardwareDiagnostics.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Rendering","namespace":"ghostrigger::domain::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"HardwareDiagnostics.from_dict","name":"from_dict","callable_type":"class_methods","line":56,"end_line":71,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderercapabilities_from_dict_line_104_185dfd96_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Rendering",
        "ghostrigger::domain::core::rendering::core::rendering::renderer_capabilities",
        "src/core/rendering/renderer_capabilities.py",
        "RendererCapabilities.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Rendering","namespace":"ghostrigger::domain::core::rendering::core::rendering::renderer_capabilities","python_file":"src/core/rendering/renderer_capabilities.py","qualname":"RendererCapabilities.from_dict","name":"from_dict","callable_type":"class_methods","line":104,"end_line":150,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderersettings_from_settings_line_68_2bcc02b5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Rendering",
        "ghostrigger::domain::core::rendering::core::rendering::renderer_settings",
        "src/core/rendering/renderer_settings.py",
        "RendererSettings.from_settings",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Rendering","namespace":"ghostrigger::domain::core::rendering::core::rendering::renderer_settings","python_file":"src/core/rendering/renderer_settings.py","qualname":"RendererSettings.from_settings","name":"from_settings","callable_type":"class_methods","line":68,"end_line":113,"signature":{"args":["cls","settings"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        hardwarediagnostics_from_dict_line_56_a66bccdf_native(),
        renderercapabilities_from_dict_line_104_185dfd96_native(),
        renderersettings_from_settings_line_68_2bcc02b5_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::rendering
