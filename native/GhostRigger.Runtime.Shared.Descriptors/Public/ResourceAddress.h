#pragma once

#include "GhostRiggerRuntimeSharedDescriptors.h"

#include <map>
#include <optional>
#include <string>

namespace ghostrigger::runtime::shared::descriptors::resource_address {

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

} // namespace ghostrigger::runtime::shared::descriptors::resource_address

extern "C" {

GR_RUNTIME_SHARED_DESCRIPTORS_API const char*
gr_runtime_shared_descriptors_resource_address_supported_schemes_json();

GR_RUNTIME_SHARED_DESCRIPTORS_API int gr_runtime_shared_descriptors_resource_address_is_supported_scheme(
    const char* scheme
);

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
);

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
);

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
);

}
