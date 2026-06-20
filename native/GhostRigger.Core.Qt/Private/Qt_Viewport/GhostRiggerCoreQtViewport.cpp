#include "../../GhostRigger.Native.Core.Foundation/Public/GhostRiggerPythonPayloadResource.h"
#include "Qt_Viewport/GhostRiggerCoreQtViewport.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"core_qt_viewport_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Qt",)"
    R"("source_package":"src/adapters/qt_viewport",)"
    R"("owner_surface":"Qt viewport adapters",)"
    R"("owner_package":"native/GhostRigger.Core.Qt",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","viewport_contracts","function_contracts"],)"
    R"("python_owns":["ui_state","runtime_policy"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"core_qt_viewport_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Qt",)"
    R"("source_package":"src/adapters/qt_viewport",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":false,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_CORE_QT_VIEWPORT_API const char* gr_core_qt_viewport_version() {
    return kVersion;
}

GHOSTRIGGER_CORE_QT_VIEWPORT_API const char* gr_core_qt_viewport_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Qt","version":"0.1.0",)"
           R"("phase":"P2 native completion","module_package":true,)"
           R"("source_package":"src/adapters/qt_viewport",)"
           R"("owner_surface":"Qt viewport adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","viewport_contracts","frame_renderer","still_frame_renderer","gizmo_renderer","camera_overlays","lighting_controller"],)"
           R"("python_fallback_required":false})";
}

GHOSTRIGGER_CORE_QT_VIEWPORT_API const char* gr_core_qt_viewport_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CORE_QT_VIEWPORT_API const char* gr_core_qt_viewport_dependency_schema_json() {
    return kDependencySchema;
}

}

