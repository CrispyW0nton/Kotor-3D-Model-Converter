#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerAssets.h"
#include "ResourceManager.h"

#include <cstring>
#include <string>

namespace resource_manager = ghostrigger::core::assets::core::assets::resource_manager;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"assets_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Assets",)"
    R"("source_package":"src/core/assets",)"
    R"("owner_surface":"Asset services",)"
    R"("owner_package":"native/GhostRigger.Core.Assets",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","resource_manager_key_contracts","resource_manager_type_tables","texture_alias_candidates"],)"
    R"("python_owns":["archive_indexing","lazy_file_reads","game_install_discovery","tpc_decoding","texture_audit_orchestration"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"assets_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Assets",)"
    R"("source_package":"src/core/assets",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_resource_manager_scope":"lookup_keys_type_tables_texture_aliases"})";

int write_output(const std::string& value, char* output, unsigned long long output_size) {
    const int required = static_cast<int>(value.size() + 1);
    if (output == nullptr || output_size == 0) {
        return required;
    }
    const unsigned long long copy_size = output_size - 1;
    const unsigned long long wanted = value.size() < copy_size ? value.size() : copy_size;
    if (wanted > 0) {
        std::memcpy(output, value.data(), static_cast<std::size_t>(wanted));
    }
    output[wanted] = '\0';
    return required;
}

} // namespace

extern "C" {

GHOSTRIGGER_ASSETS_API const char* gr_assets_version() {
    return kVersion;
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Assets","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/assets",)"
           R"("owner_surface":"Asset services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","resource_manager_keys","resource_manager_type_tables","texture_name_candidates"],)"
           R"("native_scope":"resource_manager lookup keys, type tables, and texture aliases",)"
           R"("python_fallback_reason":"archive indexing, lazy file reads, install discovery, TPC decoding, and texture audit orchestration remain Python-owned until those subsystems are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_ASSETS_API int gr_assets_resource_key(
    const char* name,
    int resource_type,
    char* output,
    unsigned long long output_size
) {
    return write_output(resource_manager::resource_key(name == nullptr ? "" : name, resource_type), output, output_size);
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_texture_name_candidates_json(const char* name) {
    static thread_local std::string candidates;
    candidates = resource_manager::texture_name_candidates_json(name == nullptr ? "" : name);
    return candidates.c_str();
}

GHOSTRIGGER_ASSETS_API int gr_assets_extension_to_resource_type(const char* extension) {
    return resource_manager::extension_to_resource_type(extension == nullptr ? "" : extension);
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_resource_type_to_extension(int resource_type) {
    return resource_manager::resource_type_to_extension(resource_type);
}

GHOSTRIGGER_ASSETS_API const char* gr_assets_resource_manager_schema_json() {
    return resource_manager::resource_manager_schema_json();
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
