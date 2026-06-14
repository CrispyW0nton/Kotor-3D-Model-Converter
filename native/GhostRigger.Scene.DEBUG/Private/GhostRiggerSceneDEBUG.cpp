#include "GhostRiggerScene.h"

#include <cstring>
#include <iostream>
#include <limits>

int main()
{
    const char* version = gr_scene_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        return 1;
    }
    const char* capabilities = gr_scene_capabilities_json();
    if (std::strstr(capabilities, R"("module_package":true)") == nullptr) {
        return 2;
    }
    if (std::strstr(capabilities, R"("native_implementation_enabled":true)") == nullptr) {
        return 3;
    }
    if (std::strstr(gr_scene_owner_boundary_json(), R"("schema":"scene_owner_boundary.v1")") == nullptr) {
        return 4;
    }
    const char* dependency_schema = gr_scene_dependency_schema_json();
    if (std::strstr(dependency_schema, R"("dependency_scan_complete":true)") == nullptr) {
        return 5;
    }
    if (std::strstr(dependency_schema, R"("python_owner_active":true)") == nullptr) {
        return 6;
    }
    if (std::strcmp(gr_scene_normalize_axis_mode("bogus"), "world") != 0) {
        return 7;
    }
    if (std::strcmp(gr_scene_axis_mode_label("local"), "Local") != 0) {
        return 8;
    }
    double basis[9] = {};
    if (gr_scene_identity_basis(basis) != 1 || basis[0] != 1.0 || basis[4] != 1.0 || basis[8] != 1.0) {
        return 9;
    }
    double fallback[3] = {9.0, 8.0, 7.0};
    double invalid[3] = {1.0, std::numeric_limits<double>::infinity(), 3.0};
    double out[3] = {};
    if (gr_scene_sanitize_vec3(invalid, fallback, out) != 1 || out[0] != 9.0 || out[1] != 8.0 || out[2] != 7.0) {
        return 10;
    }
    if (gr_scene_metadata_key_is_persisted("_runtime_model") != 0 || gr_scene_metadata_key_is_persisted("artist") != 1) {
        return 11;
    }
    std::cout << "GhostRigger.Scene.DEBUG OK: " << version << std::endl;
    return 0;
}
