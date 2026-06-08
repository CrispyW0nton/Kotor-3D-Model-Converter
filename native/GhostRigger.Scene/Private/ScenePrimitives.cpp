#include "ScenePrimitives.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cctype>
#include <string>

namespace ghostrigger::scene::core::scene::scene_primitives {
namespace {

bool vec3_is_finite(const double* values3) noexcept {
    return values3 != nullptr &&
        std::isfinite(values3[0]) &&
        std::isfinite(values3[1]) &&
        std::isfinite(values3[2]);
}

std::string trim_ascii(std::string_view value) {
    std::size_t start = 0;
    std::size_t end = value.size();
    while (start < end && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }
    return std::string(value.substr(start, end - start));
}

std::string upper_ascii(std::string_view value) {
    std::string result(value);
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char character) {
        return static_cast<char>(std::toupper(character));
    });
    return result;
}

} // namespace

Vec3 sanitize_vec3(const double* values3, Vec3 fallback) noexcept {
    if (!vec3_is_finite(values3)) {
        return fallback;
    }
    return {values3[0], values3[1], values3[2]};
}

TransformDefaults default_transform() noexcept {
    return {
        {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0},
        {1.0, 1.0, 1.0},
    };
}

PivotDefaults default_pivot() noexcept {
    return {
        {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0},
        true,
    };
}

bool pivot_values_are_valid(const double* position3, const double* rotation3) noexcept {
    return vec3_is_finite(position3) && vec3_is_finite(rotation3);
}

const char* sanitize_game_code(std::string_view value) noexcept {
    thread_local std::string key;
    key = upper_ascii(value);
    if (key.empty()) {
        return "K1";
    }
    return key.c_str();
}

const char* scene_resource_ref_defaults_json() noexcept {
    static constexpr const char* kJson =
        R"({"resource_type":"model","game":"K1","resref":"","source_path":"","source_module":"","source_archive":"","original_name":"","metadata":{}})";
    return kJson;
}

bool metadata_key_is_persisted(std::string_view key) noexcept {
    return key.rfind("_runtime", 0) != 0;
}

const char* scene_primitives_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"scene_primitives_native.v1",)"
        R"("sources":["src/core/scene/scene_object.py","src/core/scene/scene_resource_ref.py","src/core/scene/scene_object_instance.py"],)"
        R"("native_scope":["vec3 finite sanitation","Transform defaults","PivotData defaults","PivotData validity","SceneResourceRef default values","game code normalization","runtime metadata persistence filtering"],)"
        R"("python_fallback":["Python dataclass object construction","arbitrary metadata dictionaries","SceneObjectInstance nested dict serialization","material override dictionaries","legacy KMAX migration and UUID generation"],)"
        R"("reason_python_fallback":"dynamic Python object graphs and nested dictionaries remain Python-owned until KMAX serialization and scene runtime structures are ported"})";
    return kJson;
}

} // namespace ghostrigger::scene::core::scene::scene_primitives
