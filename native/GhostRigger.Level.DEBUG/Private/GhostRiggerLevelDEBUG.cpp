#include "GhostRiggerLevel.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_level_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_level_capabilities_json();
    if (std::strstr(capabilities, R"("module_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_implementation_enabled":false)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_level_owner_boundary_json(), R"("schema":"level_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* dependency_schema = gr_level_dependency_schema_json();
    if (std::strstr(dependency_schema, R"("dependency_scan_complete":true)") == nullptr) {
        return 5;
    }
    if (std::strstr(dependency_schema, R"("python_owner_active":true)") == nullptr) {
        return 6;
    }
    std::cout << "GhostRigger.Level.DEBUG OK: " << version << std::endl;
    return 0;
}