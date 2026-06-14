#include "FbxSdkSettings.h"

#include <algorithm>
#include <cctype>

namespace ghostrigger::domain::core::io::fbx::sdk_settings {
namespace {

std::string lower_copy(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    return value;
}

bool contains(const std::string& value, const char* needle) {
    return value.find(needle) != std::string::npos;
}

} // namespace

const char* fbx_download_url() noexcept {
    return "https://aps.autodesk.com/developer/overview/fbx-sdk";
}

const char* licence_notice() noexcept {
    return "Autodesk FBX SDK is an external optional dependency. GhostRigger does not bundle "
           "or redistribute Autodesk SDK files. You must download and install it separately "
           "under Autodesk's licence terms.";
}

std::string recommended_fix(const std::string& error) {
    const std::string lower = lower_copy(error);
    if (contains(lower, "dll") || contains(lower, "specified module") || contains(lower, "shared object")) {
        return "The binding was found but a required Autodesk FBX SDK library could not be loaded. Add the SDK binary/library folder for the same platform and architecture.";
    }
    if (contains(lower, "bad magic") || contains(lower, "wrong architecture") || contains(lower, "%1 is not")) {
        return "The selected FBX binding appears to target a different Python ABI or architecture. Choose bindings matching this Python major/minor version and 64-bit/32-bit architecture.";
    }
    if (contains(lower, "no module named")) {
        return "Select the folder containing Autodesk's fbx binary module and, if separate, the folder containing FbxCommon.py.";
    }
    return "Download Autodesk FBX Python SDK from Autodesk, then select binding paths matching this Python version and platform.";
}

const char* fbx_sdk_settings_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"io_fbx_sdk_settings_native.v1",)"
        R"("source":["src/io/fbx/fbx_sdk_paths.py","src/io/fbx/fbx_sdk_setup.py"],)"
        R"("native_scope":["Autodesk FBX SDK download URL","licence notice text","FBX SDK recommended-fix classification"],)"
        R"("python_fallback":["configured path existence checks","sys.path mutation","Python runtime inspection","importlib FBX probing","FbxManager/FbxScene creation","browser opening"],)"
        R"("reason_python_fallback":"runtime import probing, sys.path mutation, browser integration, and SDK object creation are process/environment-specific and remain Python-owned until an IO runtime bridge is ported"})";
    return kJson;
}

} // namespace ghostrigger::domain::core::io::fbx::sdk_settings

extern "C" {

__declspec(dllexport) const char* gr_io_fbx_sdk_download_url() {
    return ghostrigger::domain::core::io::fbx::sdk_settings::fbx_download_url();
}

__declspec(dllexport) const char* gr_io_fbx_sdk_licence_notice() {
    return ghostrigger::domain::core::io::fbx::sdk_settings::licence_notice();
}

__declspec(dllexport) const char* gr_io_fbx_sdk_recommended_fix(const char* error) {
    thread_local std::string result;
    result = ghostrigger::domain::core::io::fbx::sdk_settings::recommended_fix(error == nullptr ? "" : std::string(error));
    return result.c_str();
}

__declspec(dllexport) const char* gr_io_fbx_sdk_settings_contracts_schema_json() {
    return ghostrigger::domain::core::io::fbx::sdk_settings::fbx_sdk_settings_contracts_schema_json();
}

}
