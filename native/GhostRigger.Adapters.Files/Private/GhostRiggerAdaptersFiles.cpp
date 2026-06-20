#include "../../GhostRigger.Native.Core.Foundation/Public/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerAdaptersFiles.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"adapters_files_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Adapters.Files",)"
    R"("source_package":"src/adapters/files",)"
    R"("owner_surface":"File adapters",)"
    R"("owner_package":"native/GhostRigger.Adapters.Files",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"adapters_files_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Adapters.Files",)"
    R"("source_package":"src/adapters/files",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_version() {
    return kVersion;
}

GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_capabilities_json() {
    return R"({"name":"GhostRigger.Adapters.Files","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/adapters/files",)"
           R"("owner_surface":"File adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("local_file_writer_native":true,"local_file_writer_utf8_only":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","local_file_writer"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_dependency_schema_json() {
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
