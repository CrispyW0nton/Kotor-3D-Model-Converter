#include "GhostRiggerPythonPayloadResource.h"
#include "IO_File_Conversion/GhostRiggerConverters.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"converters_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.IO",)"
    R"("source_package":"src/converters",)"
    R"("owner_surface":"Asset converters",)"
    R"("owner_package":"native/GhostRigger.Core.IO",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","normal_map_math_contracts"],)"
    R"("python_owns":["txi_file_output","software_normal_baker_image_writes","tga_tpc_conversion","external_converter_runtime_integration","blender_fbx_bridge"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"converters_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.IO",)"
    R"("source_package":"src/converters",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_converters_scope":"normal_map_math_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_version() {
    return kVersion;
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_capabilities_json() {
    return R"({"name":"GhostRigger.Core.IO","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/converters",)"
           R"("owner_surface":"Asset converters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","normal_map_math_contracts"],)"
           R"("native_scope":"normal-map vector math, UV barycentric solve, tangent basis, world-to-tangent conversion, and ray-triangle intersection",)"
           R"("python_fallback_reason":"TXI file output, software image baking, TGA/TPC conversion, external converter runtime integration, and Blender/FBX bridge behavior remain Python-owned",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CONVERTERS_API const char* gr_converters_dependency_schema_json() {
    return kDependencySchema;
}

}

