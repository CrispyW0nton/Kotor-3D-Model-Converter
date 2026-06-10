#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::adapters::qtautorig {

const NativeFunctionImplementation& qt_application_running_line_10_869101bf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtAutorig",
        "ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs",
        "src/adapters/qt_autorig/cloth_dialogs.py",
        "_qt_application_running",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtAutorig","namespace":"ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"_qt_application_running","name":"_qt_application_running","callable_type":"module_functions","line":10,"end_line":17,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& run_cloth_preset_dialog_line_20_6033aef6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtAutorig",
        "ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs",
        "src/adapters/qt_autorig/cloth_dialogs.py",
        "run_cloth_preset_dialog",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtAutorig","namespace":"ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"run_cloth_preset_dialog","name":"run_cloth_preset_dialog","callable_type":"module_functions","line":20,"end_line":45,"signature":{"args":["parent","default_preset","title","message"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& confirm_cloth_action_line_48_c9074cd3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtAutorig",
        "ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs",
        "src/adapters/qt_autorig/cloth_dialogs.py",
        "confirm_cloth_action",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtAutorig","namespace":"ghostrigger::adapters::qtautorig::qt_autorig::cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"confirm_cloth_action","name":"confirm_cloth_action","callable_type":"module_functions","line":48,"end_line":69,"signature":{"args":["parent","title","message"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        qt_application_running_line_10_869101bf_native(),
        run_cloth_preset_dialog_line_20_6033aef6_native(),
        confirm_cloth_action_line_48_c9074cd3_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::qtautorig
