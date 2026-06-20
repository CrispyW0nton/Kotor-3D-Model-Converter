#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerGame.h"
#include "ResourceTypes.h"

namespace resource_types = ghostrigger::core::game::core::game::resource_types;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"game_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Resources.Game",)"
    R"("source_package":"src/core/game",)"
    R"("owner_surface":"Game-domain services",)"
    R"("owner_package":"native/GhostRigger.Core.Resources.Game",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","resource_type_lookup_contracts"],)"
    R"("python_owns":["tlk_reader","gff_reader","key_bif_erf_access","pykotor_loader_bridge","stock_model_import_mutation"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"game_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Resources.Game",)"
    R"("source_package":"src/core/game",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_game_scope":"resource_type_lookup_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_GAME_API const char* gr_game_version() {
    return kVersion;
}

GHOSTRIGGER_GAME_API const char* gr_game_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Resources.Game","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/game",)"
           R"("owner_surface":"Game-domain services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","resource_type_lookup_contracts"],)"
           R"("native_scope":"KotOR resource type name and extension lookup contracts",)"
           R"("python_fallback_reason":"TLK/GFF parsing, KEY/BIF/ERF access, PyKotor loading, and stock-model import normalisation remain Python-owned until validated with game-file ground truth",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_GAME_API const char* gr_game_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_GAME_API const char* gr_game_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_GAME_API const char* gr_game_resource_type_name(int resource_type) {
    return resource_types::resource_type_name(resource_type);
}

GHOSTRIGGER_GAME_API const char* gr_game_resource_type_extension(int resource_type) {
    return resource_types::resource_type_extension(resource_type);
}

GHOSTRIGGER_GAME_API const char* gr_game_resource_type_contracts_schema_json() {
    return resource_types::resource_type_contracts_schema_json();
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
