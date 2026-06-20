#pragma once

#include "GhostRiggerAdaptersGPU.h"

#include <string>
#include <vector>

namespace ghostrigger::adapters::gpu {

std::vector<std::string> gl_context_backend_candidates(const char* os_name);
int light_kind_code(const char* light_kind, bool ambient_only);

} // namespace ghostrigger::adapters::gpu

extern "C" {

GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_gl_backend_candidates_json(
    const char* os_name
);

GHOSTRIGGER_ADAPTERS_GPU_API int gr_adapters_gpu_light_kind_code(
    const char* light_kind,
    int ambient_only
);

}
