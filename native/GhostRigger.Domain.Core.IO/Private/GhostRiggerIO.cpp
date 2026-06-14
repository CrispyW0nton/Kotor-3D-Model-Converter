#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerIO.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"io_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.IO",)"
    R"("source_package":"src/io",)"
    R"("owner_surface":"Import/export IO",)"
    R"("owner_package":"native/GhostRigger.Domain.Core.IO",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","fbx_sdk_settings_contracts"],)"
    R"("python_owns":["configured_path_existence_checks","sys_path_mutation","python_runtime_inspection","importlib_fbx_probing","fbx_manager_scene_creation","browser_opening"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"io_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.IO",)"
    R"("source_package":"src/io",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_io_scope":"fbx_sdk_settings_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_IO_API const char* gr_io_version() {
    return kVersion;
}

GHOSTRIGGER_IO_API const char* gr_io_capabilities_json() {
    return R"({"name":"GhostRigger.Domain.Core.IO","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/io",)"
           R"("owner_surface":"Import/export IO","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","fbx_sdk_settings_contracts"],)"
           R"("native_scope":"FBX SDK URL/licence/recommended-fix settings contracts",)"
           R"("python_fallback_reason":"runtime import probing, sys.path mutation, browser integration, and SDK object creation remain Python-owned",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_IO_API const char* gr_io_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_IO_API const char* gr_io_dependency_schema_json() {
    return kDependencySchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
