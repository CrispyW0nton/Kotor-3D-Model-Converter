#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerSequence.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"sequence_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.Sequence",)"
    R"("source_package":"src/sequence",)"
    R"("owner_surface":"Sequence editor runtime",)"
    R"("owner_package":"native/GhostRigger.Domain.Core.Sequence",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","sequence_contracts"],)"
    R"("python_owns":["recursive value interpolation","keyframe object sorting/evaluation","track mutation","sequence serialization","asset file IO","viewport/object evaluator application","render output"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"sequence_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.Sequence",)"
    R"("source_package":"src/sequence",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_scope":["sequence_contracts"])"
    R"(})";

} // namespace

extern "C" {

GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_version() {
    return kVersion;
}

GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_capabilities_json() {
    return R"({"name":"GhostRigger.Domain.Core.Sequence","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/sequence",)"
           R"("owner_surface":"Sequence editor runtime","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","sequence_contracts"],)"
           R"("native_scope":["interpolation modes","easing curves","numeric/boolean interpolation","frame-time math"],)"
           R"("python_fallback_required":true,)"
           R"("python_fallback_reason":"Recursive values, keyframe objects, track mutation, serialization, file IO, viewport evaluator application, and rendering remain Python-owned until those runtime objects are ported together"})";
}

GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_dependency_schema_json() {
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
