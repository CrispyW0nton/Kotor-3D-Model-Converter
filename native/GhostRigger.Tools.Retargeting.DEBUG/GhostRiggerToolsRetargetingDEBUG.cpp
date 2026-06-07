#include "GhostRiggerToolsRetargeting.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_tools_retargeting_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Tools.Retargeting version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_tools_retargeting_capabilities_json();
    if (std::strstr(capabilities, R"("tool_package":true)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting capabilities missing tool package flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("owner_surface":"Retarget Workbench")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting capabilities missing owner surface" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_solve_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting enabled native solve too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_tools_retargeting_owner_boundary_json(), R"("schema":"tools_retargeting_owner_boundary.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting owner boundary mismatch" << std::endl;
        return 5;
    }
    const char* solve_packet_schema = gr_tools_retargeting_solve_packet_schema_json();
    if (std::strstr(solve_packet_schema, R"("schema":"tools_retargeting_solve_packet_schema.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting solve packet schema mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(solve_packet_schema, R"("solve_attempted":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting attempted a solve" << std::endl;
        return 7;
    }
    if (std::strstr(solve_packet_schema, R"("solve_result_count":0)") == nullptr) {
        std::cerr << "GhostRigger.Tools.Retargeting returned solve results" << std::endl;
        return 8;
    }

    std::cout << "GhostRigger.Tools.Retargeting.DEBUG OK: " << version << std::endl;
    return 0;
}
