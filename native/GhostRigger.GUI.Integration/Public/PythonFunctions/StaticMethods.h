#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_integration {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_assets_qt_matrix_background_qtmatrixpanel_normalize_crop_line_149_67abe9b7_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_integration
