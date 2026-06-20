#include "Workflow_Autorig/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::autorig {

const NativeFunctionImplementation& rigtemplate_load_line_266_0f605af1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::auto_rigger",
        "src/autorig/auto_rigger.py",
        "RigTemplate.load",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"RigTemplate.load","name":"load","callable_type":"class_methods","line":266,"end_line":297,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& clothrigpreset_names_line_204_d261924b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::cloth_rig",
        "src/autorig/cloth_rig.py",
        "ClothRigPreset.names",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::cloth_rig","python_file":"src/autorig/cloth_rig.py","qualname":"ClothRigPreset.names","name":"names","callable_type":"class_methods","line":204,"end_line":205,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& clothrigpreset_get_line_208_148424dc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::cloth_rig",
        "src/autorig/cloth_rig.py",
        "ClothRigPreset.get",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::cloth_rig","python_file":"src/autorig/cloth_rig.py","qualname":"ClothRigPreset.get","name":"get","callable_type":"class_methods","line":208,"end_line":214,"signature":{"args":["cls","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& modelorientfixer_apply_line_181_43fa93c7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::retarget_engine",
        "src/autorig/retarget_engine.py",
        "ModelOrientFixer.apply",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ModelOrientFixer.apply","name":"apply","callable_type":"class_methods","line":181,"end_line":302,"signature":{"args":["cls","model","mode","floor_snap","center_xz"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& modelorientfixer_align_to_reference_line_307_f8ff80a8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::retarget_engine",
        "src/autorig/retarget_engine.py",
        "ModelOrientFixer.align_to_reference",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ModelOrientFixer.align_to_reference","name":"align_to_reference","callable_type":"class_methods","line":307,"end_line":389,"signature":{"args":["cls","model","reference","match_floor","center_xy"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& scalesolver_solve_line_455_84919dd2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow",
        "ghostrigger::core::autorig::retarget_engine",
        "src/autorig/retarget_engine.py",
        "ScaleSolver.solve",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow","namespace":"ghostrigger::core::autorig::retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ScaleSolver.solve","name":"solve","callable_type":"class_methods","line":455,"end_line":469,"signature":{"args":["cls","src_min","src_max","ref_min","ref_max","mode","manual_factor"],"positional_count":7,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        rigtemplate_load_line_266_0f605af1_native(),
        clothrigpreset_names_line_204_d261924b_native(),
        clothrigpreset_get_line_208_148424dc_native(),
        modelorientfixer_apply_line_181_43fa93c7_native(),
        modelorientfixer_align_to_reference_line_307_f8ff80a8_native(),
        scalesolver_solve_line_455_84919dd2_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::autorig
