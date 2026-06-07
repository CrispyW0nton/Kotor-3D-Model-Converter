#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

const char* src_core_rendering_gpu_scene_helpers_compositemodel_nodes_line_292_c770f0f1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_CompositeModel.nodes","name":"nodes","kind":"properties","line":292,"end_line":293,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/rendering/gpu_scene_helpers.py", "_CompositeModel.nodes", "properties", &src_core_rendering_gpu_scene_helpers_compositemodel_nodes_line_292_c770f0f1_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
