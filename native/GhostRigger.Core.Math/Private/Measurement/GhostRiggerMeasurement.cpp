#include "GhostRiggerPythonPayloadResource.h"
#include "Measurement/GhostRiggerMeasurement.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"measurement_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Math.vcxproj",)"
    R"("source_package":"src/math;src/core/camera;src/core/geometry;src/core/measurement;src/gui/camera",)"
    R"("owner_surface":"Measurement and snapping",)"
    R"("owner_package":"native/GhostRigger.Core.Math.vcxproj",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","measurement_contracts"],)"
    R"("python_owns":["MeasurementSettings file IO","measurement overlay drawing","controller state","object dimension introspection","grid bounds calculation"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"measurement_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Math.vcxproj",)"
    R"("source_package":"src/math;src/core/camera;src/core/geometry;src/core/measurement;src/gui/camera",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_scope":["measurement_contracts"])"
    R"(})";

} // namespace

extern "C" {

GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_version() {
    return kVersion;
}

GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Math.vcxproj","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/math;src/core/camera;src/core/geometry;src/core/measurement;src/gui/camera",)"
           R"("owner_surface":"Measurement and snapping","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","measurement_contracts"],)"
           R"("native_scope":["unit conversion","distance formatting","distance parsing","angle snapping","percent snapping"],)"
           R"("python_fallback_required":true,)"
           R"("python_fallback_reason":"Settings persistence, measurement overlay drawing, controller state, object dimension introspection, and grid bounds calculation remain Python-owned until their runtime object boundaries are ported"})";
}

GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_dependency_schema_json() {
    return kDependencySchema;
}

}

