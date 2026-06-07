#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_runtime {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_qt_core_aliasloader_init_line_224_c5fe8728_descriptor_json();
const char* src_core_qt_core_aliasloader_create_module_line_227_75e53f13_descriptor_json();
const char* src_core_qt_core_aliasloader_exec_module_line_230_c94fed86_descriptor_json();
const char* src_core_qt_core_aliasfinder_find_spec_line_242_f27746af_descriptor_json();
const char* src_core_qt_core_lazymodule_init_line_257_ddb72fa4_descriptor_json();
const char* src_core_qt_core_lazymodule_load_line_262_2256a9af_descriptor_json();
const char* src_core_qt_core_lazymodule_getattr_line_272_e592785f_descriptor_json();
const char* src_core_qt_core_lazymodule_setattr_line_275_771d313f_descriptor_json();
const char* src_core_qt_core_lazymodule_delattr_line_282_8529e3e5_descriptor_json();
const char* src_core_qt_core_lazymodule_dir_line_289_97285489_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime
