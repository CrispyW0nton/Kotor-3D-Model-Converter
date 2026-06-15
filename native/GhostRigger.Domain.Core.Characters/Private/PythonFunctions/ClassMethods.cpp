#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::domain::core::characters {

const NativeFunctionImplementation& autofitoverride_from_mapping_line_72_b939c173_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Characters",
        "ghostrigger::domain::core::characters::core::characters::character_autofit_report",
        "src/core/characters/character_autofit_report.py",
        "AutoFitOverride.from_mapping",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Characters","namespace":"ghostrigger::domain::core::characters::core::characters::character_autofit_report","python_file":"src/core/characters/character_autofit_report.py","qualname":"AutoFitOverride.from_mapping","name":"from_mapping","callable_type":"class_methods","line":72,"end_line":81,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& creatureassembly_from_models_line_1193_dfce9043_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Characters",
        "ghostrigger::domain::core::characters::core::characters::creature_appearance",
        "src/core/characters/creature_appearance.py",
        "CreatureAssembly.from_models",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Characters","namespace":"ghostrigger::domain::core::characters::core::characters::creature_appearance","python_file":"src/core/characters/creature_appearance.py","qualname":"CreatureAssembly.from_models","name":"from_models","callable_type":"class_methods","line":1193,"end_line":1257,"signature":{"args":["cls","body_model","head_model","game"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& creatureassembly_from_resrefs_line_1260_9de5d9fa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Characters",
        "ghostrigger::domain::core::characters::core::characters::creature_appearance",
        "src/core/characters/creature_appearance.py",
        "CreatureAssembly.from_resrefs",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Characters","namespace":"ghostrigger::domain::core::characters::core::characters::creature_appearance","python_file":"src/core/characters/creature_appearance.py","qualname":"CreatureAssembly.from_resrefs","name":"from_resrefs","callable_type":"class_methods","line":1260,"end_line":1312,"signature":{"args":["cls","body_resref","head_resref","resource_manager","game"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& nativenodesnapshot_from_dict_line_77_23599e67_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Characters",
        "ghostrigger::domain::core::characters::core::characters::native_skeleton",
        "src/core/characters/native_skeleton.py",
        "NativeNodeSnapshot.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Characters","namespace":"ghostrigger::domain::core::characters::core::characters::native_skeleton","python_file":"src/core/characters/native_skeleton.py","qualname":"NativeNodeSnapshot.from_dict","name":"from_dict","callable_type":"class_methods","line":77,"end_line":82,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& nativeskeletonsnapshot_from_dict_line_107_3c42a345_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Characters",
        "ghostrigger::domain::core::characters::core::characters::native_skeleton",
        "src/core/characters/native_skeleton.py",
        "NativeSkeletonSnapshot.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Characters","namespace":"ghostrigger::domain::core::characters::core::characters::native_skeleton","python_file":"src/core/characters/native_skeleton.py","qualname":"NativeSkeletonSnapshot.from_dict","name":"from_dict","callable_type":"class_methods","line":107,"end_line":114,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        autofitoverride_from_mapping_line_72_b939c173_native(),
        creatureassembly_from_models_line_1193_dfce9043_native(),
        creatureassembly_from_resrefs_line_1260_9de5d9fa_native(),
        nativenodesnapshot_from_dict_line_77_23599e67_native(),
        nativeskeletonsnapshot_from_dict_line_107_3c42a345_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::characters
