#include "WorkflowBase.h"

#include <algorithm>
#include <cctype>
#include <cstring>

namespace ghostrigger::core::workflow::core::workflow::workflow_base {
namespace {

std::string lower_ascii(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (const unsigned char character : value) {
        result.push_back(static_cast<char>(std::tolower(character)));
    }
    return result;
}

std::string pluralized(int count, std::string_view singular) {
    std::string result = std::to_string(count);
    result.push_back(' ');
    result.append(singular);
    if (count != 1) {
        result.push_back('s');
    }
    return result;
}

std::string uppercase_ascii(std::string value) {
    for (char& character : value) {
        character = static_cast<char>(std::toupper(static_cast<unsigned char>(character)));
    }
    return value;
}

std::size_t last_separator(std::string_view path) {
    const std::size_t slash = path.find_last_of('/');
    const std::size_t backslash = path.find_last_of('\\');
    if (slash == std::string_view::npos) {
        return backslash;
    }
    if (backslash == std::string_view::npos) {
        return slash;
    }
    return std::max(slash, backslash);
}

} // namespace

std::string ext_of(std::string_view path) {
    const std::size_t separator = last_separator(path);
    const std::size_t search_start = separator == std::string_view::npos ? 0 : separator + 1;
    const std::size_t dot = path.find_last_of('.');
    if (dot == std::string_view::npos || dot < search_start) {
        return {};
    }
    return lower_ascii(path.substr(dot));
}

std::string resref_from_path(std::string_view path) {
    const std::size_t separator = last_separator(path);
    const std::size_t name_start = separator == std::string_view::npos ? 0 : separator + 1;
    const std::size_t dot = path.find_last_of('.');
    const std::size_t name_end = dot == std::string_view::npos || dot < name_start ? path.size() : dot;
    return lower_ascii(path.substr(name_start, name_end - name_start));
}

std::string safe_resref(std::string_view text, std::string_view fallback) {
    std::string cleaned;
    cleaned.reserve(text.size());
    for (const unsigned char character : text) {
        const unsigned char lowered = static_cast<unsigned char>(std::tolower(character));
        if (std::isalnum(lowered) || lowered == '_' || lowered == '-') {
            cleaned.push_back(static_cast<char>(lowered));
        }
    }
    return cleaned.empty() ? std::string(fallback) : cleaned;
}

std::string banner_key_for_counts(int errors, int warnings, int infos) {
    if (errors > 0) {
        return "error";
    }
    if (warnings > 0) {
        return "warning";
    }
    if (infos > 0) {
        return "info";
    }
    return "clean";
}

std::string summary_for_counts(int errors, int warnings, int infos) {
    std::string summary;
    if (errors > 0) {
        summary = pluralized(errors, "error");
    }
    if (warnings > 0) {
        if (!summary.empty()) {
            summary.append(", ");
        }
        summary.append(pluralized(warnings, "warning"));
    }
    if (infos > 0 && errors <= 0 && warnings <= 0) {
        summary = std::to_string(infos);
        summary.append(" info");
    }
    return summary.empty() ? "CLEAN" : uppercase_ascii(summary);
}

const char* workflow_base_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"workflow_base_native.v1",)"
        R"("source":"src/core/workflow/_workflow_base.py",)"
        R"("native_scope":["ext_of","resref_from_path","safe_resref","banner_key_for_counts","summary_for_counts"],)"
        R"("python_fallback":["lazy import shims","workflow dataclasses","object-list summarize_issues","blocking_codes_from_issues object inspection"],)"
        R"("reason_python_fallback":"the remaining workflow helpers inspect Python objects, dataclasses, monkeypatchable lazy imports, and per-mode workflow state"})";
    return kJson;
}

} // namespace ghostrigger::core::workflow::core::workflow::workflow_base
