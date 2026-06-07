#include "GhostRiggerToolsCharacterBuilder.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_tools_character_builder_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Tools.CharacterBuilder version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_tools_character_builder_capabilities_json();
    if (std::strstr(capabilities, R"("tool_package":true)") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder capabilities missing tool package flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("owner_surface":"Character Studio")") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder capabilities missing owner surface" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_autofit_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder enabled native autofit too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_tools_character_builder_owner_boundary_json(), R"("schema":"tools_character_builder_owner_boundary.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder owner boundary mismatch" << std::endl;
        return 5;
    }
    const char* autofit_packet_schema = gr_tools_character_builder_autofit_packet_schema_json();
    if (std::strstr(autofit_packet_schema, R"("schema":"tools_character_builder_autofit_packet_schema.v1")") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder autofit packet schema mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(autofit_packet_schema, R"("autofit_attempted":false)") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder attempted autofit work" << std::endl;
        return 7;
    }
    if (std::strstr(autofit_packet_schema, R"("autofit_result_count":0)") == nullptr) {
        std::cerr << "GhostRigger.Tools.CharacterBuilder returned autofit results" << std::endl;
        return 8;
    }

    std::cout << "GhostRigger.Tools.CharacterBuilder.DEBUG OK: " << version << std::endl;
    return 0;
}
