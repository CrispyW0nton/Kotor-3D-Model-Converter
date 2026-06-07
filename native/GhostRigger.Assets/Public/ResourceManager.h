#pragma once

#include <string>
#include <string_view>

namespace ghostrigger::assets::core::assets::resource_manager {

std::string resource_key(std::string_view name, int resource_type);
std::string texture_name_candidates_json(std::string_view name);
int extension_to_resource_type(std::string_view extension) noexcept;
const char* resource_type_to_extension(int resource_type) noexcept;
const char* resource_manager_schema_json() noexcept;

} // namespace ghostrigger::assets::core::assets::resource_manager
