#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_spritematerials {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_sequence_tracks_material_track_materialtrack_deserialize_line_51_ed9b85b8_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_spritematerials
