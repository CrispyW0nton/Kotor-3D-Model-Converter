#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRuntimeSharedResources.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Runtime.Shared.Resources","version":"0.1.0",)"
    R"("phase":"P1 foundation","shared_runtime_resources":true,)"
    R"("renderer_neutral":true,"resource_id_schema":"runtime_resource_id.v1",)"
    R"("residency_schema":"runtime_resource_residency.v1",)"
    R"("upload_packet_schema":"runtime_resource_upload_packet.v1",)"
    R"("transition_packet_schema":"runtime_resource_transition_packet.v1"})";
constexpr const char* kResourceIdSchema =
    R"({"schema":"runtime_resource_id.v1","fields":["resource_type","resource_id","generation"],)"
    R"("resource_types":["mesh_vertex_buffer","mesh_index_buffer","texture","skin_palette"]})";
constexpr const char* kResidencySchema =
    R"({"schema":"runtime_resource_residency.v1","fields":["resource_type","resource_id",)"
    R"("generation","resident","byte_count","last_upload_generation"]})";
constexpr const char* kUploadPacketSchema =
    R"({"schema":"runtime_resource_upload_packet.v1","fields":["resource_type","resource_id",)"
    R"("generation","byte_count","ready","source_generation"]})";
constexpr const char* kTransitionPacketSchema =
    R"({"schema":"runtime_resource_transition_packet.v1","fields":["resource_type","resource_id",)"
    R"("generation","from_state","to_state","already_ready"]})";

} // namespace

extern "C" {

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_version() {
    return kVersion;
}

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_capabilities_json() {
    return kCapabilities;
}

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_id_schema_json() {
    return kResourceIdSchema;
}

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_residency_schema_json() {
    return kResidencySchema;
}

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_upload_packet_schema_json() {
    return kUploadPacketSchema;
}

GR_RUNTIME_SHARED_RESOURCES_API const char* gr_runtime_shared_resources_transition_packet_schema_json() {
    return kTransitionPacketSchema;
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
