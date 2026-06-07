#include "GhostRiggerRendererModernGL.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_moderngl_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.ModernGL version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_moderngl_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_backend":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.ModernGL capabilities missing renderer backend flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("contract_version":"0.1.0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.ModernGL capabilities missing renderer contract version" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_device_owner":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.ModernGL took native device ownership too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_moderngl_backend_info_json(), R"("api":"ModernGL")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.ModernGL backend info mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_renderer_moderngl_adapter_bridge_json(), R"("fallback_backend":"python_moderngl")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.ModernGL adapter bridge mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Renderer.ModernGL.DEBUG OK: " << version << std::endl;
    return 0;
}
