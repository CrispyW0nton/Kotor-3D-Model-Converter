#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_gui_integration {

const char* src_gui_assets_qt_matrix_background_qtmatrixpanel_normalize_crop_line_149_67abe9b7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Integration","python_module":"src.gui.assets.qt_matrix_background","python_file":"src/gui/assets/qt_matrix_background.py","qualname":"QtMatrixPanel._normalize_crop","name":"_normalize_crop","kind":"static_methods","line":149,"end_line":158,"signature":{"args":["crop"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/assets/qt_matrix_background.py", "QtMatrixPanel._normalize_crop", "static_methods", &src_gui_assets_qt_matrix_background_qtmatrixpanel_normalize_crop_line_149_67abe9b7_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_integration
