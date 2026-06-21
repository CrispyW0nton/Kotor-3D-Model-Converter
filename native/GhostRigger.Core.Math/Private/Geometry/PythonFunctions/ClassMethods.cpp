#include "Geometry/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::geometry {

const NativeFunctionImplementation& kotormodel_load_line_1713_06efb4df_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "KotorModel.load",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"KotorModel.load","name":"load","callable_type":"class_methods","line":1713,"end_line":1734,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& characterscene_hook_list_for_line_2059_3faac002_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "CharacterScene._hook_list_for",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._hook_list_for","name":"_hook_list_for","callable_type":"class_methods","line":2059,"end_line":2069,"signature":{"args":["cls","model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& characterscene_facial_bone_list_for_line_2072_1a08165b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "CharacterScene._facial_bone_list_for",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._facial_bone_list_for","name":"_facial_bone_list_for","callable_type":"class_methods","line":2072,"end_line":2081,"signature":{"args":["cls","model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& characterscene_from_dict_line_2196_7e1623ef_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "CharacterScene.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene.from_dict","name":"from_dict","callable_type":"class_methods","line":2196,"end_line":2306,"signature":{"args":["cls","data","load_models"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& characterscene_from_json_line_2314_e011a172_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "CharacterScene.from_json",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene.from_json","name":"from_json","callable_type":"class_methods","line":2314,"end_line":2317,"signature":{"args":["cls","text","load_models"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        kotormodel_load_line_1713_06efb4df_native(),
        characterscene_hook_list_for_line_2059_3faac002_native(),
        characterscene_facial_bone_list_for_line_2072_1a08165b_native(),
        characterscene_from_dict_line_2196_7e1623ef_native(),
        characterscene_from_json_line_2314_e011a172_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::geometry
