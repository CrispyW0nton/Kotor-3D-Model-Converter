#include "GhostRiggerPythonPayloadResource.h"
#include "AxisMode.h"
#include "GhostRiggerScene.h"
#include "ScenePrimitives.h"

#include <array>

namespace axis_mode = ghostrigger::scene::core::scene::axis_mode;
namespace scene_primitives = ghostrigger::scene::core::scene::scene_primitives;

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
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","axis_mode_contracts","basis_math_contracts","scene_primitive_contracts"],)"
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
    R"("native_scene_scope":"axis_mode_basis_and_scene_primitive_contracts"})";

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
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","axis_mode_contracts","basis_math_contracts","scene_primitive_contracts"],)"
           R"("native_scope":"axis mode normalization, labels, finite basis validation, quaternion-to-basis conversion, scene primitive defaults, and scene persistence sanitation contracts",)"
           R"("python_fallback_reason":"TransformReferenceController, Python dataclasses, dynamic metadata dictionaries, selected object/camera references, pick-reference checks, and full KMAX serialization remain Python-owned until those runtime structures are ported",)"
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

GHOSTRIGGER_SCENE_API int gr_scene_sanitize_vec3(
    const double* values3,
    const double* fallback3,
    double* output3
) {
    if (output3 == nullptr) {
        return 0;
    }
    const scene_primitives::Vec3 fallback = fallback3 == nullptr
        ? scene_primitives::Vec3{0.0, 0.0, 0.0}
        : scene_primitives::Vec3{fallback3[0], fallback3[1], fallback3[2]};
    const auto sanitized = scene_primitives::sanitize_vec3(values3, fallback);
    output3[0] = sanitized[0];
    output3[1] = sanitized[1];
    output3[2] = sanitized[2];
    return 1;
}

GHOSTRIGGER_SCENE_API int gr_scene_transform_defaults(double* position3, double* rotation3, double* scale3) {
    if (position3 == nullptr || rotation3 == nullptr || scale3 == nullptr) {
        return 0;
    }
    const auto defaults = scene_primitives::default_transform();
    for (std::size_t index = 0; index < 3; ++index) {
        position3[index] = defaults.position[index];
        rotation3[index] = defaults.rotation[index];
        scale3[index] = defaults.scale[index];
    }
    return 1;
}

GHOSTRIGGER_SCENE_API int gr_scene_pivot_defaults(double* position3, double* rotation3, int* enabled) {
    if (position3 == nullptr || rotation3 == nullptr || enabled == nullptr) {
        return 0;
    }
    const auto defaults = scene_primitives::default_pivot();
    for (std::size_t index = 0; index < 3; ++index) {
        position3[index] = defaults.position_local[index];
        rotation3[index] = defaults.rotation_local[index];
    }
    *enabled = defaults.enabled ? 1 : 0;
    return 1;
}

GHOSTRIGGER_SCENE_API int gr_scene_pivot_values_are_valid(const double* position3, const double* rotation3) {
    return scene_primitives::pivot_values_are_valid(position3, rotation3) ? 1 : 0;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_sanitize_resource_game(const char* game) {
    return scene_primitives::sanitize_game_code(game == nullptr ? "" : game);
}

GHOSTRIGGER_SCENE_API const char* gr_scene_resource_ref_defaults_json() {
    return scene_primitives::scene_resource_ref_defaults_json();
}

GHOSTRIGGER_SCENE_API int gr_scene_metadata_key_is_persisted(const char* key) {
    return scene_primitives::metadata_key_is_persisted(key == nullptr ? "" : key) ? 1 : 0;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_primitives_schema_json() {
    return scene_primitives::scene_primitives_schema_json();
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
