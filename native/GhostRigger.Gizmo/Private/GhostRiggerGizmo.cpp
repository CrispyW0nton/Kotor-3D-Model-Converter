#include "GhostRiggerPythonPayloadResource.h"
#include "GizmoMode.h"
#include "GhostRiggerGizmo.h"

namespace gizmo_mode = ghostrigger::gizmo::core::gizmo::gizmo_mode;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"gizmo_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Gizmo",)"
    R"("source_package":"src/core/gizmo",)"
    R"("owner_surface":"Transform gizmo services",)"
    R"("owner_package":"native/GhostRigger.Gizmo",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","gizmo_mode_contracts","transform_space_contracts","gizmo_origin_resolution"],)"
    R"("python_owns":["transform_gizmo_object_state","transform_controller_drag_math","viewport_event_routing","gizmo_draw_data","runtime_object_mutation"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"gizmo_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Gizmo",)"
    R"("source_package":"src/core/gizmo",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_gizmo_scope":"mode_transform_space_and_origin_resolution_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_version() {
    return kVersion;
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_capabilities_json() {
    return R"({"name":"GhostRigger.Gizmo","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/gizmo",)"
           R"("owner_surface":"Transform gizmo services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","gizmo_mode_contracts","transform_space_contracts","gizmo_origin_resolution"],)"
           R"("native_scope":"gizmo mode values, transform space values, defaults, mode cycle order, and origin resolution",)"
           R"("python_fallback_reason":"TransformGizmo state, TransformController drag math, viewport event routing, draw data, picking, and object mutation remain Python-owned until those subsystems are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_normalize_mode(const char* mode) {
    return gizmo_mode::gizmo_mode_to_string(gizmo_mode::normalize_gizmo_mode(mode == nullptr ? "" : mode));
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_cycle_mode(const char* mode) {
    return gizmo_mode::gizmo_mode_to_string(
        gizmo_mode::cycle_gizmo_mode(gizmo_mode::normalize_gizmo_mode(mode == nullptr ? "" : mode))
    );
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_mode_values_json() {
    return gizmo_mode::gizmo_mode_values_json();
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_normalize_transform_space(const char* space) {
    return gizmo_mode::transform_space_to_string(
        gizmo_mode::normalize_transform_space(space == nullptr ? "" : space)
    );
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_transform_space_values_json() {
    return gizmo_mode::transform_space_values_json();
}

GHOSTRIGGER_GIZMO_API const char* gr_gizmo_mode_contracts_schema_json() {
    return gizmo_mode::gizmo_mode_contracts_schema_json();
}

GHOSTRIGGER_GIZMO_API int gr_gizmo_resolve_origin(
    const double* position,
    const double* pivot_world,
    const double* gizmo_world,
    int has_pivot_world,
    int has_gizmo_world,
    int is_helper_object,
    int affect_pivot_only,
    double* out_origin
) {
    return gizmo_mode::resolve_gizmo_origin(
        position,
        pivot_world,
        gizmo_world,
        has_pivot_world != 0,
        has_gizmo_world != 0,
        is_helper_object != 0,
        affect_pivot_only != 0,
        out_origin
    )
        ? 1
        : 0;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
