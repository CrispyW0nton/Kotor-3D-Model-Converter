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

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_roundtrip_line_568_cd29482e_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_compute_adjacency_line_631_816fefe7_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_pack_line_665_044477c6_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
