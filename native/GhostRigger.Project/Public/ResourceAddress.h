#pragma once

#include <map>
#include <optional>
#include <string>

namespace ghostrigger::project::core::project::resource_address {

struct ResourceAddress {
    std::string scheme;
    std::optional<std::string> game;
    std::optional<std::string> module_id;
    std::optional<std::string> resref;
    std::optional<std::string> restype;
    std::optional<std::string> layer;
    std::optional<std::string> path;
    std::optional<std::string> object_id;
    std::optional<std::string> fragment;
    std::map<std::string, std::string> metadata;

    ResourceAddress(
        std::string address_scheme,
        std::optional<std::string> address_game = std::nullopt,
        std::optional<std::string> address_module_id = std::nullopt,
        std::optional<std::string> address_resref = std::nullopt,
        std::optional<std::string> address_restype = std::nullopt,
        std::optional<std::string> address_layer = std::nullopt,
        std::optional<std::string> address_path = std::nullopt,
        std::optional<std::string> address_object_id = std::nullopt,
        std::optional<std::string> address_fragment = std::nullopt,
        std::map<std::string, std::string> address_metadata = {}
    );

    std::string stable_key() const;
    std::string display_name() const;
    std::string to_json() const;
};

bool is_supported_scheme(const std::string& scheme);
std::string supported_schemes_json();
const char* resource_address_contracts_schema_json() noexcept;

} // namespace ghostrigger::project::core::project::resource_address
