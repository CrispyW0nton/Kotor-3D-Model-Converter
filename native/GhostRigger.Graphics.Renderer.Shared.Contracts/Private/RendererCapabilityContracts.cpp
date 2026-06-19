#include "RendererCapabilityContracts.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string trimmed(const char* value) {
    if (value == nullptr) {
        return {};
    }
    std::string text(value);
    const auto first = std::find_if_not(text.begin(), text.end(), [](unsigned char ch) {
        return std::isspace(ch) != 0;
    });
    const auto last = std::find_if_not(text.rbegin(), text.rend(), [](unsigned char ch) {
        return std::isspace(ch) != 0;
    }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::string normalized_key(const char* value) {
    std::string text = trimmed(value);
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
        if (ch == '-' || ch == ' ') {
            return '_';
        }
        return static_cast<char>(std::tolower(ch));
    });
    return text;
}

std::string lower_trimmed(const char* value) {
    std::string text = trimmed(value);
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return text;
}

std::string escape_json_string(const std::string& value) {
    std::ostringstream out;
    for (const unsigned char ch : value) {
        if (ch == '"' || ch == '\\') {
            out << '\\' << static_cast<char>(ch);
        } else {
            out << static_cast<char>(ch);
        }
    }
    return out.str();
}

std::string string_array_json(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            out << ',';
        }
        out << '"' << escape_json_string(values[i]) << '"';
    }
    out << ']';
    return out.str();
}

std::vector<std::string> split_supported_modes(const char* supported_modes) {
    std::vector<std::string> modes;
    std::string current;
    const std::string text = supported_modes == nullptr ? std::string() : std::string(supported_modes);
    for (const char ch : text) {
        if (ch == ',' || ch == ';' || ch == '|') {
            const std::string mode = lower_trimmed(current.c_str());
            if (!mode.empty()) {
                modes.push_back(mode);
            }
            current.clear();
        } else {
            current.push_back(ch);
        }
    }
    const std::string mode = lower_trimmed(current.c_str());
    if (!mode.empty()) {
        modes.push_back(mode);
    }
    return modes;
}

bool contains(const std::vector<std::string>& values, const std::string& value) {
    return std::find(values.begin(), values.end(), value) != values.end();
}

} // namespace

namespace ghostrigger::graphics::renderer::shared::contracts {

std::string normalize_display_mode(const char* value) {
    const std::string key = normalized_key(value);
    if (key == "wire" || key == "wireframe") {
        return "wireframe";
    }
    if (key == "hidden" || key == "hidden_line") {
        return "hidden_line";
    }
    if (key == "solid" || key == "flat") {
        return "solid";
    }
    if (key == "shaded") {
        return "shaded";
    }
    if (key == "smooth" || key == "smooth_shaded") {
        return "smooth_shaded";
    }
    if (key == "texture" || key == "textured") {
        return "textured";
    }
    if (key == "lightmapped" || key == "textured_lightmapped") {
        return "textured_lightmapped";
    }
    if (key == "realistic" || key == "full" || key == "full_material") {
        return "full_material";
    }
    if (key == "bounds" || key == "bounding_box") {
        return "bounding_box";
    }
    if (key == "normals" || key == "normals_debug") {
        return "normals_debug";
    }
    if (key == "uv" || key == "uv_debug") {
        return "uv_debug";
    }
    return "full_material";
}

std::vector<std::string> moderngl_display_modes() {
    return {
        "wireframe",
        "hidden_line",
        "solid",
        "shaded",
        "smooth_shaded",
        "textured",
        "textured_lightmapped",
        "full_material",
        "bounding_box",
        "normals_debug",
        "uv_debug",
    };
}

std::vector<std::string> wgpu_display_modes() {
    return {
        "wireframe",
        "hidden_line",
        "solid",
        "shaded",
        "smooth_shaded",
        "textured",
        "textured_lightmapped",
        "full_material",
        "bounding_box",
        "normals_debug",
        "uv_debug",
    };
}

std::string wgpu_fallback_display_modes_json() {
    return R"({"full_material":"textured_lightmapped","bounding_box":"solid","normals_debug":"shaded","uv_debug":"textured"})";
}

std::vector<std::string> diagnostic_display_modes() {
    return {"solid"};
}

std::string status_text(bool available, bool diagnostic_only, const char* reason) {
    if (available) {
        return diagnostic_only ? "Available (diagnostic only)" : "Available";
    }
    const std::string why = trimmed(reason).empty() ? "not supported" : trimmed(reason);
    return "Unavailable: " + why;
}

bool supports_display_mode(bool available, bool diagnostic_only, const char* supported_modes, const char* mode) {
    if (!available) {
        return false;
    }
    const std::vector<std::string> modes = split_supported_modes(supported_modes);
    if (modes.empty()) {
        return !diagnostic_only;
    }
    return contains(modes, lower_trimmed(mode));
}

} // namespace ghostrigger::graphics::renderer::shared::contracts

extern "C" {

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_normalize_display_mode(const char* value) {
    static thread_local std::string mode;
    mode = ghostrigger::graphics::renderer::shared::contracts::normalize_display_mode(value);
    return mode.c_str();
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_moderngl_display_modes_json() {
    static thread_local std::string modes;
    modes = string_array_json(ghostrigger::graphics::renderer::shared::contracts::moderngl_display_modes());
    return modes.c_str();
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_display_modes_json() {
    static thread_local std::string modes;
    modes = string_array_json(ghostrigger::graphics::renderer::shared::contracts::wgpu_display_modes());
    return modes.c_str();
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_fallback_display_modes_json() {
    static thread_local std::string fallbacks;
    fallbacks = ghostrigger::graphics::renderer::shared::contracts::wgpu_fallback_display_modes_json();
    return fallbacks.c_str();
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_diagnostic_display_modes_json() {
    static thread_local std::string modes;
    modes = string_array_json(ghostrigger::graphics::renderer::shared::contracts::diagnostic_display_modes());
    return modes.c_str();
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_status_text(
    int available,
    int diagnostic_only,
    const char* reason
) {
    static thread_local std::string status;
    status = ghostrigger::graphics::renderer::shared::contracts::status_text(available != 0, diagnostic_only != 0, reason);
    return status.c_str();
}

GR_RENDERER_CONTRACTS_API int gr_renderer_contracts_supports_display_mode(
    int available,
    int diagnostic_only,
    const char* supported_modes,
    const char* mode
) {
    return ghostrigger::graphics::renderer::shared::contracts::supports_display_mode(
        available != 0,
        diagnostic_only != 0,
        supported_modes,
        mode
    ) ? 1 : 0;
}

}
