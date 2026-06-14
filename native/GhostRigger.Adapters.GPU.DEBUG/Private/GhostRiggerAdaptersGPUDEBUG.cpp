#include "GhostRiggerAdaptersGPU.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_adapters_gpu_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_adapters_gpu_capabilities_json();
    if (std::strstr(capabilities, R"("module_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_implementation_enabled":true)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_adapters_gpu_owner_boundary_json(), R"("schema":"adapters_gpu_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* dependency_schema = gr_adapters_gpu_dependency_schema_json();
    if (std::strstr(dependency_schema, R"("dependency_scan_complete":true)") == nullptr) {
        return 5;
    }
    if (std::strstr(dependency_schema, R"("python_owner_active":true)") == nullptr) {
        return 6;
    }
    const char* windows_backends = gr_adapters_gpu_gl_backend_candidates_json("nt");
    if (std::strstr(windows_backends, R"(["default","wgl","egl"])") == nullptr) {
        return 7;
    }
    const char* linux_backends = gr_adapters_gpu_gl_backend_candidates_json("posix");
    if (std::strstr(linux_backends, R"(["egl","default","x11"])") == nullptr) {
        return 8;
    }
    if (gr_adapters_gpu_light_kind_code("directional", 0) != 2) {
        return 9;
    }
    std::cout << "GhostRigger.Adapters.GPU.DEBUG OK: " << version << std::endl;
    return 0;
}
