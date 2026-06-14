#include "GhostRiggerGizmo.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_gizmo_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_gizmo_capabilities_json();
    if (std::strstr(capabilities, R"("module_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_implementation_enabled":true)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_gizmo_owner_boundary_json(), R"("schema":"gizmo_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* dependency_schema = gr_gizmo_dependency_schema_json();
    if (std::strstr(dependency_schema, R"("dependency_scan_complete":true)") == nullptr) {
        return 5;
    }
    if (std::strstr(dependency_schema, R"("python_owner_active":true)") == nullptr) {
        return 6;
    }
    if (std::strcmp(gr_gizmo_normalize_mode("not-real"), "translate") != 0) {
        return 7;
    }
    if (std::strcmp(gr_gizmo_cycle_mode("scale"), "translate") != 0) {
        return 8;
    }
    if (std::strcmp(gr_gizmo_normalize_transform_space("not-real"), "world") != 0) {
        return 9;
    }
    std::cout << "GhostRigger.Gizmo.DEBUG OK: " << version << std::endl;
    return 0;
}
