#include "GhostRiggerPythonPayloadResource.h"
#include "Scripting/GhostRiggerCoreAutomationScripting.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"core_automation_scripting_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Automation.vcxproj",)"
    R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
    R"("owner_surface":"Script adapters",)"
    R"("owner_package":"native/GhostRigger.Core.Automation.vcxproj",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"core_automation_scripting_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Automation.vcxproj",)"
    R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_version() {
    return kVersion;
}

GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Automation.vcxproj","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
           R"("owner_surface":"Script adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("unavailable_compiler_native":true,)"
           R"("script_compiler_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","unavailable_compiler_result","unavailable_compiler_validation_issue"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CORE_AUTOMATION_SCRIPTING_API const char* gr_core_automation_scripting_dependency_schema_json() {
    return kDependencySchema;
}

}

