#include "GhostRiggerPythonPayloadResource.h"
#include "TwoDA/GhostRiggerTemplates.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"templates_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.IO",)"
    R"("source_package":"src/core/mdl;src/io/fbx;src/formats;src/core/templates",)"
    R"("owner_surface":"Template services",)"
    R"("owner_package":"native/GhostRigger.Core.IO",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","template_version_contracts","template_count_contracts","twoda_utility_contracts"],)"
    R"("python_owns":["kotor_model_construction","placeholder_mesh_construction","manifest_file_writes","pykotor_animation_validation","eyeball_node_inspection","twoda_table_parsing","twoda_cache_game_library_access"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"templates_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.IO",)"
    R"("source_package":"src/core/mdl;src/io/fbx;src/formats;src/core/templates",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("python_fallback_reason":"Model construction, PyKotor validation, table/file parsing, and cache access depend on runtime geometry objects, game files, or filesystem state that should be ported as dedicated validated slices"})";

} // namespace

extern "C" {

GHOSTRIGGER_TEMPLATES_API const char* gr_templates_version() {
    return kVersion;
}

GHOSTRIGGER_TEMPLATES_API const char* gr_templates_capabilities_json() {
    return R"({"name":"GhostRigger.Core.IO","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/mdl;src/io/fbx;src/formats;src/core/templates",)"
           R"("owner_surface":"Template services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("templates_contracts_native":true,"templates_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","template_version_contracts","template_count_contracts","twoda_utility_contracts"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_TEMPLATES_API const char* gr_templates_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_TEMPLATES_API const char* gr_templates_dependency_schema_json() {
    return kDependencySchema;
}

}

