#include "GhostRiggerWindowsLevelEditor.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_windows_level_editor_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_windows_level_editor_capabilities_json();
    if (std::strstr(capabilities, R"("window_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_shell_enabled":false)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_windows_level_editor_owner_boundary_json(), R"("schema":"windows_level_editor_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* schema = gr_windows_level_editor_host_service_schema_json();
    if (std::strstr(schema, R"("host_module_registered":false)") == nullptr) {
        return 5;
    }
    if (std::strstr(schema, R"("visible_shell_mutation_allowed":false)") == nullptr) {
        return 6;
    }
    std::cout << "GhostRigger.Windows.LevelEditor.DEBUG OK: " << version << std::endl;
    return 0;
}
