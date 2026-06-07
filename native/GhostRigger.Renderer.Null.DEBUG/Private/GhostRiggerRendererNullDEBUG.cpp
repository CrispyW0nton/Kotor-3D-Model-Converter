#include "GhostRiggerRendererNull.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_null_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.Null version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_null_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_backend":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Null capabilities missing renderer backend flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("contract_version":"0.1.0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Null capabilities missing renderer contract version" << std::endl;
        return 3;
    }
    if (std::strstr(gr_renderer_null_backend_info_json(), R"("api":"null")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Null backend info mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_null_dry_run_frame_stats_json(), R"("backend_id":"renderer_null")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.Null dry-run frame stats mismatch" << std::endl;
        return 5;
    }

    std::cout << "GhostRigger.Renderer.Null.DEBUG OK: " << version << std::endl;
    return 0;
}
