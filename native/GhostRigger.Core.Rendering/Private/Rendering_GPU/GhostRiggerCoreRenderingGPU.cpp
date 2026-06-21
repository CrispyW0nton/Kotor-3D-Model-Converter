#include "../../GhostRigger.Native.Core.Foundation/Public/GhostRiggerPythonPayloadResource.h"
#include "Rendering_GPU/GhostRiggerCoreRenderingGPU.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"core_rendering_gpu_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering",)"
    R"("source_package":"src/adapters/gpu",)"
    R"("owner_surface":"GPU adapters",)"
    R"("owner_package":"native/GhostRigger.Core.Rendering",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"core_rendering_gpu_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering",)"
    R"("source_package":"src/adapters/gpu",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_version() {
    return kVersion;
}

GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Rendering","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/adapters/gpu",)"
           R"("owner_surface":"GPU adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("gpu_adapter_contracts_native":true,)"
           R"("gpu_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","gl_backend_candidates","light_kind_code"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_dependency_schema_json() {
    return kDependencySchema;
}

}

