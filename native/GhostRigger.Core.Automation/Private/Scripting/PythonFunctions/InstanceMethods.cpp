#include "Scripting/PythonFunctions/InstanceMethods.h"

namespace ghostrigger::core::automation::scripting {

const NativeFunctionImplementation& unavailablescriptcompiler_compile_script_line_29_00747c15_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.vcxproj",
        "ghostrigger::core::automation::scripting::unavailable_compiler",
        "src/adapters/scripts/unavailable_compiler.py",
        "UnavailableScriptCompiler.compile_script",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.vcxproj","namespace":"ghostrigger::core::automation::scripting::unavailable_compiler","python_file":"src/adapters/scripts/unavailable_compiler.py","qualname":"UnavailableScriptCompiler.compile_script","name":"compile_script","callable_type":"instance_methods","line":29,"end_line":46,"signature":{"args":["self","source","game"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        unavailablescriptcompiler_compile_script_line_29_00747c15_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::automation::scripting
