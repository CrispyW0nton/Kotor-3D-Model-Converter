#include "GhostRiggerToolsExport.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_tools_export_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Tools.Export version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_tools_export_capabilities_json();
    if (std::strstr(capabilities, R"("tool_package":true)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export capabilities missing tool package flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("owner_surface":"Export and validation workflow")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export capabilities missing owner surface" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_write_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export enabled native writes too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_tools_export_owner_boundary_json(), R"("schema":"tools_export_owner_boundary.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export owner boundary mismatch" << std::endl;
        return 5;
    }
    const char* preflight_packet_schema = gr_tools_export_preflight_packet_schema_json();
    if (std::strstr(preflight_packet_schema, R"("schema":"tools_export_preflight_packet_schema.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export preflight packet schema mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(preflight_packet_schema, R"("preflight_attempted":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export attempted preflight work" << std::endl;
        return 7;
    }
    if (std::strstr(preflight_packet_schema, R"("preflight_result_count":0)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Export returned preflight results" << std::endl;
        return 8;
    }

    std::cout << "GhostRigger.Tools.Export.DEBUG OK: " << version << std::endl;
    return 0;
}
