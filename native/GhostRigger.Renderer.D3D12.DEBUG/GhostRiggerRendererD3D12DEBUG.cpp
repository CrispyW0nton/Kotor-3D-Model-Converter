#include "GhostRiggerRendererD3D12.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_d3d12_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.D3D12 version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_d3d12_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_backend":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 capabilities missing renderer backend flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("contract_version":"0.1.0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 capabilities missing renderer contract version" << std::endl;
        return 3;
    }
    if (std::strstr(gr_renderer_d3d12_backend_info_json(), R"("api":"d3d12")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 backend info mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_d3d12_device_requirements_json(), R"("minimum_feature_level":"12_0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 device requirements mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_renderer_d3d12_dry_run_frame_stats_json(), R"("backend_id":"renderer_d3d12")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 dry-run frame stats mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Renderer.D3D12.DEBUG OK: " << version << std::endl;
    return 0;
}
