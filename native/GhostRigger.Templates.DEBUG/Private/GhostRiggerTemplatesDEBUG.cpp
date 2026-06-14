#include "GhostRiggerTemplates.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_templates_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_templates_capabilities_json();
    if (std::strstr(capabilities, R"("module_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_implementation_enabled":true)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_templates_owner_boundary_json(), R"("schema":"templates_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* dependency_schema = gr_templates_dependency_schema_json();
    if (std::strstr(dependency_schema, R"("dependency_scan_complete":true)") == nullptr) {
        return 5;
    }
    if (std::strstr(dependency_schema, R"("python_owner_active":true)") == nullptr) {
        return 6;
    }
    if (std::strcmp(gr_templates_normalize_game_version("k2"), "K2") != 0) {
        return 7;
    }
    if (gr_templates_humanoid_bone_count("K1") != 64 || gr_templates_humanoid_animation_slot_count("K2") != 76) {
        return 8;
    }
    if (std::strcmp(gr_templates_detect_twoda_format(reinterpret_cast<const unsigned char*>("2DA V2.0\n"), 9), "ascii_v2") != 0) {
        return 9;
    }
    if (std::strstr(gr_templates_split_twoda_line_json("0 c_bastila ****"), R"(["0","c_bastila",""])") == nullptr) {
        return 10;
    }
    std::cout << "GhostRigger.Templates.DEBUG OK: " << version << std::endl;
    return 0;
}
