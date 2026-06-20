#pragma once

#include "Rendering_Contracts/GhostRiggerRendererContracts.h"

#include <string>
#include <vector>

namespace ghostrigger::core::rendering::contracts {

std::string normalize_display_mode(const char* value);
std::vector<std::string> moderngl_display_modes();
std::vector<std::string> wgpu_display_modes();
std::string wgpu_fallback_display_modes_json();
std::vector<std::string> diagnostic_display_modes();
std::string status_text(bool available, bool diagnostic_only, const char* reason);
bool supports_display_mode(bool available, bool diagnostic_only, const char* supported_modes, const char* mode);

} // namespace ghostrigger::core::rendering::contracts

extern "C" {
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_normalize_display_mode(const char* value);
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_moderngl_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_fallback_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_diagnostic_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_status_text(
    int available,
    int diagnostic_only,
    const char* reason
);
GR_RENDERER_CONTRACTS_API int gr_renderer_contracts_supports_display_mode(
    int available,
    int diagnostic_only,
    const char* supported_modes,
    const char* mode
);
}
