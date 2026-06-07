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
    if (std::strstr(gr_renderer_d3d12_adapter_probe_json(), R"("schema":"renderer_d3d12_adapter_probe.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 adapter probe mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(gr_renderer_d3d12_device_readiness_json(), R"("schema":"renderer_d3d12_device_readiness.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 device readiness mismatch" << std::endl;
        return 7;
    }
    if (std::strstr(gr_renderer_d3d12_queue_swap_chain_readiness_json(), R"("schema":"renderer_d3d12_queue_swap_chain_readiness.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 queue/swap-chain readiness mismatch" << std::endl;
        return 8;
    }
    if (std::strstr(gr_renderer_d3d12_failure_diagnostics_json(), R"("schema":"renderer_d3d12_failure_diagnostics.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 failure diagnostics mismatch" << std::endl;
        return 9;
    }
    if (std::strstr(gr_renderer_d3d12_dry_run_frame_stats_json(), R"("backend_id":"renderer_d3d12")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 dry-run frame stats mismatch" << std::endl;
        return 10;
    }

    std::cout << "GhostRigger.Renderer.D3D12.DEBUG OK: " << version << std::endl;
    return 0;
}
