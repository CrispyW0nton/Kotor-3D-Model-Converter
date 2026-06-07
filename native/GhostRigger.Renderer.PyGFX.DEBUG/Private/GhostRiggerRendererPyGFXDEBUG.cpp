#include "GhostRiggerRendererPyGFX.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_pygfx_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.PyGFX version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_pygfx_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_backend":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.PyGFX capabilities missing renderer backend flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("contract_version":"0.1.0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.PyGFX capabilities missing renderer contract version" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_device_owner":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.PyGFX took native device ownership too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_pygfx_backend_info_json(), R"("api":"PyGFX/WGPU")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.PyGFX backend info mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_renderer_pygfx_adapter_bridge_json(), R"("fallback_backend":"python_pygfx")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.PyGFX adapter bridge mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Renderer.PyGFX.DEBUG OK: " << version << std::endl;
    return 0;
}
