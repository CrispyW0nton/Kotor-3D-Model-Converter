#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerConverters.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"converters_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Converters",)"
    R"("source_package":"src/converters",)"
    R"("owner_surface":"Asset converters",)"
    R"("owner_package":"native/GhostRigger.Converters",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"converters_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Converters",)"
    R"("source_package":"src/converters",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_version() {
    return kVersion;
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_capabilities_json() {
    return R"({"name":"GhostRigger.Converters","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/converters",)"
           R"("owner_surface":"Asset converters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_dependency_schema_json() {
    return kDependencySchema;
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
