#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

const char* src_core_rendering_hardware_info_hardwarediagnostics_from_dict_line_56_a66bccdf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"HardwareDiagnostics.from_dict","name":"from_dict","kind":"class_methods","line":56,"end_line":71,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/rendering/hardware_info.py", "HardwareDiagnostics.from_dict", "class_methods", &src_core_rendering_hardware_info_hardwarediagnostics_from_dict_line_56_a66bccdf_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
