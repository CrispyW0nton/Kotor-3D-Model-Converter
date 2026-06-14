#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerWalkmesh.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"walkmesh_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.Walkmesh",)"
    R"("source_package":"src/core/walkmesh",)"
    R"("owner_surface":"Walkmesh editing",)"
    R"("owner_package":"native/GhostRigger.Domain.Core.Walkmesh",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","walkmesh_surface_contracts"],)"
    R"("python_owns":["WOK object traversal","walkmesh face mutation","walkmesh validation","walkmesh roundtrip serialization","overlay draw-list generation","FBX face grouping"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"walkmesh_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.Walkmesh",)"
    R"("source_package":"src/core/walkmesh",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_scope":["walkmesh_surface_contracts"])"
    R"(})";

} // namespace

extern "C" {

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_version() {
    return kVersion;
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_capabilities_json() {
    return R"({"name":"GhostRigger.Domain.Core.Walkmesh","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/walkmesh",)"
           R"("owner_surface":"Walkmesh editing","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","walkmesh_surface_contracts"],)"
           R"("native_scope":["surface names","overlay colors","walkability flags","FBX material metadata"],)"
           R"("python_fallback_required":true,)"
           R"("python_fallback_reason":"WOK traversal, mutation, validation, serialization, draw-list construction, and export grouping remain Python-owned until game-file walkmesh fixtures validate their native ports"})";
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_dependency_schema_json() {
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
