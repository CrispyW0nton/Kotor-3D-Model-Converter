#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRuntimeSharedContracts.h"

#include "GhostRiggerNativeCoreFoundation.h"

extern "C" {

const char* gr_runtime_shared_contracts_version()
{
    return "0.1.0";
}

const char* gr_runtime_shared_contracts_capabilities_json()
{
    return R"json({"package":"GhostRigger.Runtime.Shared","version":"0.1.0","native_core_version":"0.1.0","renderer_neutral_contracts":true,"shared_runtime_contracts":true,"python_detectable":true})json";
}

const char* gr_runtime_shared_contracts_renderer_descriptor_json()
{
    (void)gr_native_core_version();
    return R"json({"contract":"renderer_neutral","version":"0.1.0","owns_device":false,"owns_window":false,"payloads":["version","capabilities","renderer_descriptor"],"future_payloads":["scene_handles","resource_residency","draw_submission","frame_statistics"]})json";
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
