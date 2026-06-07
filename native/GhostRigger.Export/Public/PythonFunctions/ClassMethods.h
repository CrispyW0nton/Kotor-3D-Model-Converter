#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_export {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_export_gltf_importer_glbreader_from_file_line_140_8725bc1b_descriptor_json();
const char* src_core_export_gltf_importer_glbreader_from_bytes_line_144_89250c96_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_export
