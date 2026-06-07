#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRetargeting.h"
#include "RetargetContracts.h"

#include <cstring>
#include <string>

namespace retarget_contracts = ghostrigger::retargeting::core::retargeting::retarget_contracts;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"retargeting_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Retargeting",)"
    R"("source_package":"src/core/retargeting",)"
    R"("owner_surface":"Retarget Workbench core",)"
    R"("owner_package":"native/GhostRigger.Retargeting",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","retarget_mode_contracts","retarget_output_name_validation"],)"
    R"("python_owns":["solver_runtime","animation_slot_resolution","target_model_inspection","fbx_export_pipeline","workflow_policy","ui_state"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"retargeting_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Retargeting",)"
    R"("source_package":"src/core/retargeting",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_retargeting_scope":"mode_contracts_output_name_validation"})";

int write_output(const std::string& value, char* output, unsigned long long output_size) {
    const int required = static_cast<int>(value.size() + 1);
    if (output == nullptr || output_size == 0) {
        return required;
    }
    const unsigned long long copy_size = output_size - 1;
    const unsigned long long wanted = value.size() < copy_size ? value.size() : copy_size;
    if (wanted > 0) {
        std::memcpy(output, value.data(), static_cast<std::size_t>(wanted));
    }
    output[wanted] = '\0';
    return required;
}

} // namespace

extern "C" {

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_version() {
    return kVersion;
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_capabilities_json() {
    return R"({"name":"GhostRigger.Retargeting","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/retargeting",)"
           R"("owner_surface":"Retarget Workbench core","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","retarget_mode_contracts","retarget_output_name_validation"],)"
           R"("native_scope":"retarget mode contracts and output-name validation",)"
           R"("python_fallback_reason":"slot resolution, target model inspection, solver runtime, and export pipelines remain Python-owned until those subsystems are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_coerce_mode(const char* mode) {
    return retarget_contracts::retarget_mode_to_string(
        retarget_contracts::coerce_retarget_mode(mode == nullptr ? "" : mode)
    );
}

GHOSTRIGGER_RETARGETING_API int gr_retargeting_is_kotor_output_mode(const char* mode) {
    return retarget_contracts::is_kotor_output_mode(mode == nullptr ? "" : mode) ? 1 : 0;
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_mode_specs_json() {
    return retarget_contracts::retarget_mode_specs_json();
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_coerce_kotor_output_name_mode(const char* mode) {
    return retarget_contracts::kotor_output_name_mode_to_string(
        retarget_contracts::coerce_kotor_output_name_mode(mode == nullptr ? "" : mode)
    );
}

GHOSTRIGGER_RETARGETING_API int gr_retargeting_validate_custom_kotor_animation_name(
    const char* name,
    char* output,
    unsigned long long output_size
) {
    return write_output(retarget_contracts::validate_custom_kotor_animation_name(name == nullptr ? "" : name), output, output_size);
}

GHOSTRIGGER_RETARGETING_API int gr_retargeting_validate_unreal_clip_name(
    const char* name,
    char* output,
    unsigned long long output_size
) {
    return write_output(retarget_contracts::validate_unreal_clip_name(name == nullptr ? "" : name), output, output_size);
}

GHOSTRIGGER_RETARGETING_API const char* gr_retargeting_contracts_schema_json() {
    return retarget_contracts::retarget_contracts_schema_json();
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
