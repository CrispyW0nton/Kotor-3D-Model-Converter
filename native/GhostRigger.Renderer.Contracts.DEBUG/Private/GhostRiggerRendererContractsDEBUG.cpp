#include "GhostRiggerRendererContracts.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_contracts_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.Contracts version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_contracts_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_contracts":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Contracts capabilities missing renderer contracts flag" << std::endl;
        return 2;
    }
    if (std::strstr(gr_renderer_contracts_backend_schema_json(), R"("schema":"renderer_backend.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Contracts backend schema mismatch" << std::endl;
        return 3;
    }
    if (std::strstr(gr_renderer_contracts_surface_schema_json(), R"("schema":"renderer_surface.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Contracts surface schema mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_contracts_draw_item_schema_json(), R"("schema":"renderer_draw_item.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Contracts draw item schema mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_renderer_contracts_frame_stats_schema_json(), R"("schema":"renderer_frame_stats.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Contracts frame stats schema mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Renderer.Contracts.DEBUG OK: " << version << std::endl;
    return 0;
}
