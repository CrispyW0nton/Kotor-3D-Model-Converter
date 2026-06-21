#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::runtime::core::host {

const NativeFunctionImplementation& make_package_line_293_8ece9a00_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Core.Host.vcxproj",
        "ghostrigger::runtime::core::host::core::qt_core",
        "src/core/qt_core.py",
        "_make_package",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Core.Host.vcxproj","namespace":"ghostrigger::runtime::core::host::core::qt_core","python_file":"src/core/qt_core.py","qualname":"_make_package","name":"_make_package","callable_type":"module_functions","line":293,"end_line":297,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& register_alias_line_300_993b5427_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Core.Host.vcxproj",
        "ghostrigger::runtime::core::host::core::qt_core",
        "src/core/qt_core.py",
        "_register_alias",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Core.Host.vcxproj","namespace":"ghostrigger::runtime::core::host::core::qt_core","python_file":"src/core/qt_core.py","qualname":"_register_alias","name":"_register_alias","callable_type":"module_functions","line":300,"end_line":307,"signature":{"args":["alias","target"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& register_group_line_310_731fa624_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Core.Host.vcxproj",
        "ghostrigger::runtime::core::host::core::qt_core",
        "src/core/qt_core.py",
        "_register_group",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Core.Host.vcxproj","namespace":"ghostrigger::runtime::core::host::core::qt_core","python_file":"src/core/qt_core.py","qualname":"_register_group","name":"_register_group","callable_type":"module_functions","line":310,"end_line":324,"signature":{"args":["group","modules"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        make_package_line_293_8ece9a00_native(),
        register_alias_line_300_993b5427_native(),
        register_group_line_310_731fa624_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::runtime::core::host
