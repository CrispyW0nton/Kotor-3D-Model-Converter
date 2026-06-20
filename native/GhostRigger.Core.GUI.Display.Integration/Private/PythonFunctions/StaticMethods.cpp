#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::gui::integration {

const NativeFunctionImplementation& qtmatrixpanel_normalize_crop_line_149_67abe9b7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display.Integration",
        "ghostrigger::core::gui::integration::assets::qt_matrix_background",
        "src/gui/assets/qt_matrix_background.py",
        "QtMatrixPanel._normalize_crop",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display.Integration","namespace":"ghostrigger::core::gui::integration::assets::qt_matrix_background","python_file":"src/gui/assets/qt_matrix_background.py","qualname":"QtMatrixPanel._normalize_crop","name":"_normalize_crop","callable_type":"static_methods","line":149,"end_line":158,"signature":{"args":["crop"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        qtmatrixpanel_normalize_crop_line_149_67abe9b7_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::integration
