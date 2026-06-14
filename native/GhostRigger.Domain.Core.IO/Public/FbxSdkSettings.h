#pragma once

#include <string>

namespace ghostrigger::domain::core::io::fbx::sdk_settings {

const char* fbx_download_url() noexcept;
const char* licence_notice() noexcept;
std::string recommended_fix(const std::string& error);
const char* fbx_sdk_settings_contracts_schema_json() noexcept;

} // namespace ghostrigger::domain::core::io::fbx::sdk_settings
