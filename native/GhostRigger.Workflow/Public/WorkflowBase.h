#pragma once

#include <string>
#include <string_view>

namespace ghostrigger::workflow::core::workflow::workflow_base {

std::string ext_of(std::string_view path);
std::string resref_from_path(std::string_view path);
std::string safe_resref(std::string_view text, std::string_view fallback = "untitled");
std::string banner_key_for_counts(int errors, int warnings, int infos);
std::string summary_for_counts(int errors, int warnings, int infos);
const char* workflow_base_schema_json() noexcept;

} // namespace ghostrigger::workflow::core::workflow::workflow_base
