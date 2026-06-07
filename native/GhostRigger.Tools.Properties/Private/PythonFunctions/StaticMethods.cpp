#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_properties {

const char* src_gui_panels_module_editor_module_editor_properties_moduleeditorpropertiespanel_set_vector_line_85_4910d35b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Properties","python_module":"src.gui.panels.module_editor.module_editor_properties","python_file":"src/gui/panels/module_editor/module_editor_properties.py","qualname":"ModuleEditorPropertiesPanel._set_vector","name":"_set_vector","kind":"static_methods","line":85,"end_line":87,"signature":{"args":["boxes","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/panels/module_editor/module_editor_properties.py", "ModuleEditorPropertiesPanel._set_vector", "static_methods", &src_gui_panels_module_editor_module_editor_properties_moduleeditorpropertiespanel_set_vector_line_85_4910d35b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_properties
