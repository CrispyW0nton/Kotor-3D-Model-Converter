#pragma once

#include "GhostRiggerCoreRenderingGPU.h"

#include <string>
#include <vector>

namespace ghostrigger::core::rendering::gpu {

std::vector<std::string> gl_context_backend_candidates(const char* os_name);
int light_kind_code(const char* light_kind, bool ambient_only);

} // namespace ghostrigger::core::rendering::gpu

extern "C" {

GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_gl_backend_candidates_json(
    const char* os_name
);

GHOSTRIGGER_CORE_RENDERING_GPU_API int gr_core_rendering_gpu_light_kind_code(
    const char* light_kind,
    int ambient_only
);

}
