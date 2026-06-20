#include "GpuAdapterContracts.h"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cctype>
#include <memory>
#include <sstream>
#include <string_view>

namespace ghostrigger::adapters::gpu {
namespace {

constexpr const char* kGlBackendEnv = "GHOSTRIGGER_GL_BACKEND";

std::string lower_trimmed(std::string_view value) {
    std::size_t begin = 0;
    std::size_t end = value.size();
    while (begin < end && std::isspace(static_cast<unsigned char>(value[begin]))) {
        ++begin;
    }
    while (end > begin && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }
    std::string result;
    result.reserve(end - begin);
    for (std::size_t index = begin; index < end; ++index) {
        result.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(value[index]))));
    }
    return result;
}

bool contains(std::string_view value, std::string_view needle) {
    return value.find(needle) != std::string_view::npos;
}

std::string environment_value(const char* name) {
#ifdef _WIN32
    char* raw_value = nullptr;
    std::size_t value_size = 0;
    if (_dupenv_s(&raw_value, &value_size, name) != 0 || raw_value == nullptr) {
        return {};
    }
    std::unique_ptr<char, decltype(&std::free)> value(raw_value, &std::free);
    return std::string(value.get(), value_size == 0 ? 0 : value_size - 1);
#else
    if (const char* raw_value = std::getenv(name)) {
        return raw_value;
    }
    return {};
#endif
}

} // namespace

std::vector<std::string> gl_context_backend_candidates(const char* os_name) {
    const std::string override_backend = lower_trimmed(environment_value(kGlBackendEnv));
    if (!override_backend.empty()) {
        return {override_backend};
    }

    const std::string platform = lower_trimmed(os_name == nullptr ? "" : os_name);
    if (platform == "nt") {
        return {"default", "wgl", "egl"};
    }
    if (platform == "posix") {
        return {"egl", "default", "x11"};
    }
    return {"default"};
}

int light_kind_code(const char* light_kind, bool ambient_only) {
    const std::string kind = lower_trimmed(light_kind == nullptr ? "point" : light_kind);
    if (contains(kind, "ambient") || ambient_only) {
        return 4;
    }
    if (contains(kind, "directional")) {
        return 2;
    }
    if (contains(kind, "area")) {
        return 3;
    }
    if (contains(kind, "spot")) {
        return 1;
    }
    return 0;
}

} // namespace ghostrigger::adapters::gpu

namespace {

std::string json_string_array(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) {
            out << ',';
        }
        out << '"';
        for (const char ch : values[index]) {
            if (ch == '"' || ch == '\\') {
                out << '\\';
            }
            out << ch;
        }
        out << '"';
    }
    out << ']';
    return out.str();
}

} // namespace

extern "C" {

GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_gl_backend_candidates_json(
    const char* os_name
) {
    static thread_local std::string json;
    json = json_string_array(ghostrigger::adapters::gpu::gl_context_backend_candidates(os_name));
    return json.c_str();
}

GHOSTRIGGER_ADAPTERS_GPU_API int gr_adapters_gpu_light_kind_code(
    const char* light_kind,
    int ambient_only
) {
    return ghostrigger::adapters::gpu::light_kind_code(light_kind, ambient_only != 0);
}

}
