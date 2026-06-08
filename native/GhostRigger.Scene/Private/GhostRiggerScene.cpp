#include "GhostRiggerPythonPayloadResource.h"
#include "AxisMode.h"
#include "GhostRiggerScene.h"

#include <array>

namespace axis_mode = ghostrigger::scene::core::scene::axis_mode;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"scene_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Scene",)"
    R"("source_package":"src/core/scene",)"
    R"("owner_surface":"Main Viewport / KMAX scene services",)"
    R"("owner_package":"native/GhostRigger.Scene",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","axis_mode_contracts","basis_math_contracts"],)"
    R"("python_owns":["scene_graph_runtime","object_lifetime","workflow_policy","ui_state","dynamic_camera_object_references"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"scene_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Scene",)"
    R"("source_package":"src/core/scene",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_scene_scope":"axis_mode_and_basis_contracts"})";

void write_basis(const axis_mode::Matrix3& basis, double* output_basis9) {
    if (output_basis9 == nullptr) {
        return;
    }
    for (std::size_t index = 0; index < basis.size(); ++index) {
        output_basis9[index] = basis[index];
    }
}

} // namespace

extern "C" {

GHOSTRIGGER_SCENE_API const char* gr_scene_version() {
    return kVersion;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_capabilities_json() {
    return R"({"name":"GhostRigger.Scene","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/scene",)"
           R"("owner_surface":"Main Viewport / KMAX scene services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","axis_mode_contracts","basis_math_contracts"],)"
           R"("native_scope":"axis mode normalization, labels, finite basis validation, and quaternion-to-basis conversion",)"
           R"("python_fallback_reason":"TransformReferenceController still needs Python scene, camera, selected object, parent, and pick-reference objects until those runtime structures are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_SCENE_API const char* gr_scene_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_normalize_axis_mode(const char* mode) {
    return axis_mode::axis_mode_to_string(axis_mode::normalize_axis_mode(mode == nullptr ? "" : mode));
}

GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_label(const char* mode) {
    return axis_mode::axis_mode_label(axis_mode::normalize_axis_mode(mode == nullptr ? "" : mode));
}

GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_values_json() {
    return axis_mode::axis_mode_values_json();
}

GHOSTRIGGER_SCENE_API int gr_scene_identity_basis(double* output_basis9) {
    if (output_basis9 == nullptr) {
        return 0;
    }
    write_basis(axis_mode::identity_basis(), output_basis9);
    return 1;
}

GHOSTRIGGER_SCENE_API int gr_scene_finite_basis(const double* basis9, double* output_basis9) {
    if (output_basis9 == nullptr) {
        return 0;
    }
    write_basis(axis_mode::finite_basis(basis9), output_basis9);
    return 1;
}

GHOSTRIGGER_SCENE_API int gr_scene_quat_to_basis(const double* quat4, double* output_basis9) {
    if (output_basis9 == nullptr) {
        return 0;
    }
    write_basis(axis_mode::quat_to_basis(quat4), output_basis9);
    return 1;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_contracts_schema_json() {
    return axis_mode::axis_mode_contracts_schema_json();
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
