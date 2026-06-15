#include "PythonFunctions/Properties.h"

namespace ghostrigger::tools::workflow::sceneinformation {

const NativeFunctionImplementation& axismode_label_line_25_7f940ea5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SceneInformation",
        "ghostrigger::tools::workflow::sceneinformation::core::scene::axis_mode",
        "src/core/scene/axis_mode.py",
        "AxisMode.label",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SceneInformation","namespace":"ghostrigger::tools::workflow::sceneinformation::core::scene::axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.label","name":"label","callable_type":"properties","line":25,"end_line":26,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& kmaxscene_display_name_line_43_4c4f5179_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SceneInformation",
        "ghostrigger::tools::workflow::sceneinformation::core::scene::kmax_scene",
        "src/core/scene/kmax_scene.py",
        "KMaxScene.display_name",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SceneInformation","namespace":"ghostrigger::tools::workflow::sceneinformation::core::scene::kmax_scene","python_file":"src/core/scene/kmax_scene.py","qualname":"KMaxScene.display_name","name":"display_name","callable_type":"properties","line":43,"end_line":46,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& moduleroomplacement_group_id_line_26_2739f71f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SceneInformation",
        "ghostrigger::tools::workflow::sceneinformation::core::scene::module_scene_import",
        "src/core/scene/module_scene_import.py",
        "ModuleRoomPlacement.group_id",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SceneInformation","namespace":"ghostrigger::tools::workflow::sceneinformation::core::scene::module_scene_import","python_file":"src/core/scene/module_scene_import.py","qualname":"ModuleRoomPlacement.group_id","name":"group_id","callable_type":"properties","line":26,"end_line":27,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pivotdata_position_line_54_fa472186_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SceneInformation",
        "ghostrigger::tools::workflow::sceneinformation::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "PivotData.position",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SceneInformation","namespace":"ghostrigger::tools::workflow::sceneinformation::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.position","name":"position","callable_type":"properties","line":54,"end_line":55,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pivotdata_rotation_line_62_8f4a7cea_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SceneInformation",
        "ghostrigger::tools::workflow::sceneinformation::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "PivotData.rotation",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SceneInformation","namespace":"ghostrigger::tools::workflow::sceneinformation::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.rotation","name":"rotation","callable_type":"properties","line":62,"end_line":63,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        axismode_label_line_25_7f940ea5_native(),
        kmaxscene_display_name_line_43_4c4f5179_native(),
        moduleroomplacement_group_id_line_26_2739f71f_native(),
        pivotdata_position_line_54_fa472186_native(),
        pivotdata_rotation_line_62_8f4a7cea_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::workflow::sceneinformation
