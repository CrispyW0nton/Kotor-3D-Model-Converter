#include "ResourceAddress.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <filesystem>
#include <sstream>
#include <string_view>
#include <utility>
#include <vector>

namespace ghostrigger::runtime::core::host::shared::descriptors::resource_address {
namespace {

constexpr std::array<std::string_view, 11> kSupportedSchemes = {
    "game_resource",
    "module_resource",
    "override_resource",
    "project_resource",
    "local_file",
    "generated_output",
    "kmap_object",
    "kmax_object",
    "retarget_profile",
    "preview_result",
    "export_candidate",
};

std::string trim(std::string value) {
    auto is_not_space = [](unsigned char value) {
        return std::isspace(value) == 0;
    };
    value.erase(value.begin(), std::find_if(value.begin(), value.end(), is_not_space));
    value.erase(std::find_if(value.rbegin(), value.rend(), is_not_space).base(), value.end());
    return value;
}

std::optional<std::string> clean_optional_text(
    std::optional<std::string> value,
    bool upper = false,
    bool lower = false
) {
    if (!value.has_value()) {
        return std::nullopt;
    }

    std::string text = trim(*value);
    if (text.empty()) {
        return std::nullopt;
    }

    if (upper) {
        std::transform(text.begin(), text.end(), text.begin(), [](unsigned char character) {
            return static_cast<char>(std::toupper(character));
        });
    } else if (lower) {
        std::transform(text.begin(), text.end(), text.begin(), [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        });
    }

    return text;
}

std::optional<std::string> optional_from_c_string(const char* value) {
    if (value == nullptr) {
        return std::nullopt;
    }
    return std::string(value);
}

void append_join_part(std::vector<std::string>& parts, const std::optional<std::string>& value) {
    if (value.has_value() && !value->empty()) {
        parts.push_back(*value);
    }
}

void append_join_part(std::vector<std::string>& parts, const std::string& value) {
    if (!value.empty()) {
        parts.push_back(value);
    }
}

std::string join_colon(const std::vector<std::string>& parts) {
    std::ostringstream output;
    for (std::size_t index = 0; index < parts.size(); ++index) {
        if (index > 0) {
            output << ':';
        }
        output << parts[index];
    }
    return output.str();
}

std::string join_slash(const std::vector<std::string>& parts) {
    std::ostringstream output;
    for (std::size_t index = 0; index < parts.size(); ++index) {
        if (index > 0) {
            output << '/';
        }
        output << parts[index];
    }
    return output.str();
}

std::string json_escape(const std::string& value) {
    std::ostringstream output;
    for (const char character : value) {
        switch (character) {
        case '\\':
            output << "\\\\";
            break;
        case '"':
            output << "\\\"";
            break;
        case '\b':
            output << "\\b";
            break;
        case '\f':
            output << "\\f";
            break;
        case '\n':
            output << "\\n";
            break;
        case '\r':
            output << "\\r";
            break;
        case '\t':
            output << "\\t";
            break;
        default:
            output << character;
            break;
        }
    }
    return output.str();
}

void append_json_field(
    std::ostringstream& output,
    const char* key,
    const std::optional<std::string>& value,
    bool& first
) {
    if (!first) {
        output << ',';
    }
    first = false;
    output << '"' << key << "\":";
    if (value.has_value()) {
        output << '"' << json_escape(*value) << '"';
    } else {
        output << "null";
    }
}

void append_json_field(std::ostringstream& output, const char* key, const std::string& value, bool& first) {
    if (!first) {
        output << ',';
    }
    first = false;
    output << '"' << key << "\":\"" << json_escape(value) << '"';
}

std::string basename_for_display(const std::string& path) {
    const std::filesystem::path parsed(path);
    const std::string filename = parsed.filename().string();
    if (!filename.empty()) {
        return filename;
    }
    return path;
}

ResourceAddress make_address_from_c_args(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
) {
    return ResourceAddress(
        std::string(scheme == nullptr ? "" : scheme),
        optional_from_c_string(game),
        optional_from_c_string(module_id),
        optional_from_c_string(resref),
        optional_from_c_string(restype),
        optional_from_c_string(layer),
        optional_from_c_string(path),
        optional_from_c_string(object_id),
        optional_from_c_string(fragment)
    );
}

} // namespace

ResourceAddress::ResourceAddress(
    std::string address_scheme,
    std::optional<std::string> address_game,
    std::optional<std::string> address_module_id,
    std::optional<std::string> address_resref,
    std::optional<std::string> address_restype,
    std::optional<std::string> address_layer,
    std::optional<std::string> address_path,
    std::optional<std::string> address_object_id,
    std::optional<std::string> address_fragment,
    std::map<std::string, std::string> address_metadata
) :
    scheme(clean_optional_text(std::move(address_scheme), false, true).value_or("")),
    game(clean_optional_text(std::move(address_game), false, true)),
    module_id(clean_optional_text(std::move(address_module_id), false, true)),
    resref(clean_optional_text(std::move(address_resref))),
    restype(clean_optional_text(std::move(address_restype), true, false)),
    layer(clean_optional_text(std::move(address_layer), false, true)),
    path(clean_optional_text(std::move(address_path))),
    object_id(clean_optional_text(std::move(address_object_id))),
    fragment(clean_optional_text(std::move(address_fragment))),
    metadata(std::move(address_metadata)) {
    if (restype.has_value() && !restype->empty() && restype->front() == '.') {
        restype = restype->substr(1);
        restype = clean_optional_text(std::move(restype), true, false);
    }
}

std::string ResourceAddress::stable_key() const {
    std::vector<std::string> parts;
    if (scheme == "module_resource") {
        append_join_part(parts, scheme);
        append_join_part(parts, game);
        append_join_part(parts, module_id);
        append_join_part(parts, layer);
        append_join_part(parts, restype);
        append_join_part(parts, resref);
        return join_colon(parts);
    }

    if (
        scheme == "game_resource" ||
        scheme == "override_resource" ||
        scheme == "project_resource" ||
        scheme == "generated_output"
    ) {
        append_join_part(parts, scheme);
        append_join_part(parts, game);
        append_join_part(parts, layer);
        append_join_part(parts, restype);
        append_join_part(parts, resref);
        append_join_part(parts, path);
        return join_colon(parts);
    }

    if (scheme == "kmap_object" || scheme == "kmax_object") {
        append_join_part(parts, scheme);
        append_join_part(parts, object_id);
        append_join_part(parts, fragment);
        return join_colon(parts);
    }

    if (scheme == "local_file") {
        return scheme + ":" + path.value_or("");
    }

    append_join_part(parts, scheme);
    append_join_part(parts, game);
    append_join_part(parts, module_id);
    append_join_part(parts, layer);
    append_join_part(parts, restype);
    append_join_part(parts, resref);
    append_join_part(parts, object_id);
    append_join_part(parts, path);
    append_join_part(parts, fragment);
    return join_colon(parts);
}

std::string ResourceAddress::display_name() const {
    if (resref.has_value() && restype.has_value()) {
        std::string restype_lower = *restype;
        std::transform(restype_lower.begin(), restype_lower.end(), restype_lower.begin(), [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        });

        const std::string label = *resref + "." + restype_lower;
        std::vector<std::string> context_parts;
        append_join_part(context_parts, game);
        append_join_part(context_parts, module_id);
        append_join_part(context_parts, layer);
        const std::string context = join_slash(context_parts);
        if (!context.empty()) {
            return label + " (" + context + ")";
        }
        return label;
    }

    if (path.has_value()) {
        return basename_for_display(*path);
    }

    if (object_id.has_value()) {
        return *object_id;
    }

    if (!scheme.empty()) {
        return scheme;
    }

    return "resource";
}

std::string ResourceAddress::to_json() const {
    std::ostringstream output;
    bool first = true;
    output << '{';
    append_json_field(output, "scheme", scheme, first);
    append_json_field(output, "game", game, first);
    append_json_field(output, "module_id", module_id, first);
    append_json_field(output, "resref", resref, first);
    append_json_field(output, "restype", restype, first);
    append_json_field(output, "layer", layer, first);
    append_json_field(output, "path", path, first);
    append_json_field(output, "object_id", object_id, first);
    append_json_field(output, "fragment", fragment, first);
    if (!first) {
        output << ',';
    }
    output << "\"metadata\":{";
    bool first_metadata = true;
    for (const auto& [key, value] : metadata) {
        if (!first_metadata) {
            output << ',';
        }
        first_metadata = false;
        output << '"' << json_escape(key) << "\":\"" << json_escape(value) << '"';
    }
    output << "}}";
    return output.str();
}

bool is_supported_scheme(const std::string& scheme) {
    const std::string cleaned = clean_optional_text(scheme, false, true).value_or("");
    return std::any_of(kSupportedSchemes.begin(), kSupportedSchemes.end(), [&cleaned](std::string_view known_scheme) {
        return cleaned == known_scheme;
    });
}

std::string supported_schemes_json() {
    std::ostringstream output;
    output << '[';
    for (std::size_t index = 0; index < kSupportedSchemes.size(); ++index) {
        if (index > 0) {
            output << ',';
        }
        output << '"' << kSupportedSchemes[index] << '"';
    }
    output << ']';
    return output.str();
}

} // namespace ghostrigger::runtime::core::host::shared::descriptors::resource_address

extern "C" {

GR_RUNTIME_SHARED_DESCRIPTORS_API const char*
gr_runtime_shared_descriptors_resource_address_supported_schemes_json() {
    static const std::string schemes =
        ghostrigger::runtime::core::host::shared::descriptors::resource_address::supported_schemes_json();
    return schemes.c_str();
}

GR_RUNTIME_SHARED_DESCRIPTORS_API int gr_runtime_shared_descriptors_resource_address_is_supported_scheme(
    const char* scheme
) {
    return ghostrigger::runtime::core::host::shared::descriptors::resource_address::is_supported_scheme(
        std::string(scheme == nullptr ? "" : scheme)
    ) ? 1 : 0;
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_stable_key(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
) {
    thread_local std::string result;
    result = ghostrigger::runtime::core::host::shared::descriptors::resource_address::make_address_from_c_args(
        scheme,
        game,
        module_id,
        resref,
        restype,
        layer,
        path,
        object_id,
        fragment
    ).stable_key();
    return result.c_str();
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_display_name(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
) {
    thread_local std::string result;
    result = ghostrigger::runtime::core::host::shared::descriptors::resource_address::make_address_from_c_args(
        scheme,
        game,
        module_id,
        resref,
        restype,
        layer,
        path,
        object_id,
        fragment
    ).display_name();
    return result.c_str();
}

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_to_json(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
) {
    thread_local std::string result;
    result = ghostrigger::runtime::core::host::shared::descriptors::resource_address::make_address_from_c_args(
        scheme,
        game,
        module_id,
        resref,
        restype,
        layer,
        path,
        object_id,
        fragment
    ).to_json();
    return result.c_str();
}

}
