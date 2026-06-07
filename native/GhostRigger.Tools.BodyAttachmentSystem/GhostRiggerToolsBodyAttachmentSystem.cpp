#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsBodyAttachmentSystem.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_body_attachment_system_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.BodyAttachmentSystem",)"
    R"("owner_surface":"Body Attachment System",)"
    R"("owner_package":"native/GhostRigger.Tools.BodyAttachmentSystem",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["attachment_packet_metadata","socket_follow_contracts","bas_runtime_diagnostics"],)"
    R"("python_owns":["bas_ui","attachment_recipe_authoring","socket_selection_policy","visible_workflow"],)"
    R"("native_attachment_eval_enabled":false})";
constexpr const char* kAttachmentPacketSchema =
    R"({"schema":"tools_body_attachment_system_attachment_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.BodyAttachmentSystem",)"
    R"("diagnostic_only":true,"native_attachment_eval_enabled":false,)"
    R"("input_packets":["body_resref","attachment_layers","socket_targets","local_offsets"],)"
    R"("output_packets":["attachment_world_matrices","socket_diagnostics","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["body_handle_missing","socket_missing","native_attachment_eval_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_version() {
    return kVersion;
}

GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.BodyAttachmentSystem","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Body Attachment System","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_attachment_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","attachment_packet_schema","socket_follow_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_BODY_ATTACHMENT_SYSTEM_API const char* gr_tools_body_attachment_system_attachment_packet_schema_json() {
    return kAttachmentPacketSchema;
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
