#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::tools::sequenceeditor {

const NativeFunctionImplementation& animationworkflowmixin_build_baked_animation_samples_for_node_line_501_8b43e701_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.SequenceEditor",
        "ghostrigger::tools::sequenceeditor::gui::windows::application_core::shared::animation_workflow",
        "src/gui/windows/application_core/shared/animation_workflow.py",
        "AnimationWorkflowMixin._build_baked_animation._samples_for_node",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.SequenceEditor","namespace":"ghostrigger::tools::sequenceeditor::gui::windows::application_core::shared::animation_workflow","python_file":"src/gui/windows/application_core/shared/animation_workflow.py","qualname":"AnimationWorkflowMixin._build_baked_animation._samples_for_node","name":"_samples_for_node","callable_type":"nested_functions","line":501,"end_line":505,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        animationworkflowmixin_build_baked_animation_samples_for_node_line_501_8b43e701_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::sequenceeditor
