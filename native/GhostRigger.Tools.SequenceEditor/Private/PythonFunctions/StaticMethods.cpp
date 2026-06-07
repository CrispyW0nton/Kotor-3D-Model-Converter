#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor {

const char* src_gui_windows_application_core_shared_animation_workflow_animationworkflowmixin_is_head_animation_slot_line_278_daa495fc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.gui.windows.application_core.shared.animation_workflow","python_file":"src/gui/windows/application_core/shared/animation_workflow.py","qualname":"AnimationWorkflowMixin._is_head_animation_slot","name":"_is_head_animation_slot","kind":"static_methods","line":278,"end_line":280,"signature":{"args":["anim_name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_sequence_sequence_manager_sequencemanager_safe_filename_line_174_6e8e07fc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.sequence_manager","python_file":"src/sequence/sequence_manager.py","qualname":"SequenceManager.safe_filename","name":"safe_filename","kind":"static_methods","line":174,"end_line":177,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/windows/application_core/shared/animation_workflow.py", "AnimationWorkflowMixin._is_head_animation_slot", "static_methods", &src_gui_windows_application_core_shared_animation_workflow_animationworkflowmixin_is_head_animation_slot_line_278_daa495fc_descriptor_json},
        {"src/sequence/sequence_manager.py", "SequenceManager.safe_filename", "static_methods", &src_sequence_sequence_manager_sequencemanager_safe_filename_line_174_6e8e07fc_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor
