#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_tools_bodyattachmentsystem {

const char* src_core_characters_headless_body_workflow_bodyguideedithistory_can_undo_line_3233_965ab5fb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.BodyAttachmentSystem","python_module":"src.core.characters.headless_body_workflow","python_file":"src/core/characters/headless_body_workflow.py","qualname":"BodyGuideEditHistory.can_undo","name":"can_undo","kind":"properties","line":3233,"end_line":3234,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_characters_headless_body_workflow_bodyguideedithistory_can_redo_line_3237_68214687_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.BodyAttachmentSystem","python_module":"src.core.characters.headless_body_workflow","python_file":"src/core/characters/headless_body_workflow.py","qualname":"BodyGuideEditHistory.can_redo","name":"can_redo","kind":"properties","line":3237,"end_line":3238,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/characters/headless_body_workflow.py", "BodyGuideEditHistory.can_undo", "properties", &src_core_characters_headless_body_workflow_bodyguideedithistory_can_undo_line_3233_965ab5fb_descriptor_json},
        {"src/core/characters/headless_body_workflow.py", "BodyGuideEditHistory.can_redo", "properties", &src_core_characters_headless_body_workflow_bodyguideedithistory_can_redo_line_3237_68214687_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_bodyattachmentsystem
