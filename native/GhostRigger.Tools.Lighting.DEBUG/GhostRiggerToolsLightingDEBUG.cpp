#include "GhostRiggerToolsLighting.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_tools_lighting_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_tools_lighting_capabilities_json();
    if (std::strstr(capabilities, R"("tool_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_light_eval_enabled":false)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_tools_lighting_owner_boundary_json(), R"("schema":"tools_lighting_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* schema = gr_tools_lighting_light_packet_schema_json();
    if (std::strstr(schema, R"("query_attempted":false)") == nullptr) {
        return 5;
    }
    if (std::strstr(schema, R"("result_count":0)") == nullptr) {
        return 6;
    }
    std::cout << "GhostRigger.Tools.Lighting.DEBUG OK: " << version << std::endl;
    return 0;
}
