#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerAdaptersQtAutorig.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"adapters_qt_autorig_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Adapters.QtAutorig",)"
    R"("source_package":"src/adapters/qt_autorig",)"
    R"("owner_surface":"Qt auto-rig adapters",)"
    R"("owner_package":"native/GhostRigger.Adapters.QtAutorig",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","cloth_dialog_contracts"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"adapters_qt_autorig_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Adapters.QtAutorig",)"
    R"("source_package":"src/adapters/qt_autorig",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_version() {
    return kVersion;
}

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_capabilities_json() {
    return R"({"name":"GhostRigger.Adapters.QtAutorig","version":"0.1.0",)"
           R"("phase":"P2 native completion","module_package":true,)"
           R"("source_package":"src/adapters/qt_autorig",)"
           R"("owner_surface":"Qt auto-rig adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","cloth_dialogs"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_dependency_schema_json() {
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
