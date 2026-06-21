#include "GhostRiggerPythonPayloadResource.h"
#include "Shared_Descriptors/GhostRiggerRuntimeSharedDescriptors.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Runtime.Shared","version":"0.1.0",)"
    R"("phase":"P1 foundation","shared_runtime_descriptors":true,)"
    R"("renderer_neutral":true,"mesh_schema":"runtime_mesh_descriptor.v1",)"
    R"("material_schema":"runtime_material_descriptor.v1","frame_schema":"runtime_frame_descriptor.v1",)"
    R"("native_resource_address":true,"native_resource_address_schema":"resource_address.v1",)"
    R"("python_fallback_secondary":true})";
constexpr const char* kMeshSchema =
    R"({"schema":"runtime_mesh_descriptor.v1","fields":["native_mesh_id","vertex_count",)"
    R"("index_count","material_slot","bounds_min_xyz","bounds_max_xyz","flags"]})";
constexpr const char* kMaterialSchema =
    R"({"schema":"runtime_material_descriptor.v1","fields":["material_slot","flags",)"
    R"("base_color_rgba","diffuse_texture_id","lightmap_texture_id"]})";
constexpr const char* kFrameSchema =
    R"({"schema":"runtime_frame_descriptor.v1","fields":["frame_index","viewport_width",)"
    R"("viewport_height","visible_mesh_count","draw_call_count","dirty_resource_count"]})";

} // namespace

extern "C" {

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_version() {
    return kVersion;
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_capabilities_json() {
    return kCapabilities;
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_mesh_schema_json() {
    return kMeshSchema;
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_material_schema_json() {
    return kMaterialSchema;
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_frame_schema_json() {
    return kFrameSchema;
}

}

