#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::runtime::core::host::shared::contracts {

const NativeFunctionImplementation& nativeruntimebinding_load_line_703_925af164_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared",
        "ghostrigger::runtime::core::host::shared::contracts::adapters::rendering::native_core::binding",
        "src/adapters/rendering/native_core/binding.py",
        "NativeRuntimeBinding.load",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared","namespace":"ghostrigger::runtime::core::host::shared::contracts::adapters::rendering::native_core::binding","python_file":"src/adapters/rendering/native_core/binding.py","qualname":"NativeRuntimeBinding.load","name":"load","callable_type":"class_methods","line":703,"end_line":719,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderercapabilities_from_dict_line_104_185dfd96_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared",
        "ghostrigger::runtime::core::host::shared::contracts::core::rendering::renderer_capabilities",
        "src/core/rendering/renderer_capabilities.py",
        "RendererCapabilities.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared","namespace":"ghostrigger::runtime::core::host::shared::contracts::core::rendering::renderer_capabilities","python_file":"src/core/rendering/renderer_capabilities.py","qualname":"RendererCapabilities.from_dict","name":"from_dict","callable_type":"class_methods","line":104,"end_line":150,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        nativeruntimebinding_load_line_703_925af164_native(),
        renderercapabilities_from_dict_line_104_185dfd96_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::runtime::core::host::shared::contracts
