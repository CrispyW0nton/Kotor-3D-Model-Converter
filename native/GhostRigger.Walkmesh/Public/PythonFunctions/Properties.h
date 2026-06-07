#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_walkmesh {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_color_line_151_366a94f0_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_normal_line_155_2b51a16b_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_visible_line_753_0e217618_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_key_line_814_e16bcb57_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_overlay_count_line_819_771599f7_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
