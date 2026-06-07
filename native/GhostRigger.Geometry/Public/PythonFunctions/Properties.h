#pragma once

#include <cstddef>

namespace ghostrigger::geometry {

#ifndef GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& modeltaxonomy_display_name_line_181_50864de3_native();
const NativeFunctionImplementation& charactermode_display_name_line_256_6ffae90b_native();
const NativeFunctionImplementation& charactermode_icon_key_line_261_6d6ba368_native();
const NativeFunctionImplementation& modelnode_is_mesh_line_861_87a3e698_native();
const NativeFunctionImplementation& modelnode_is_skin_line_863_0c5e9483_native();
const NativeFunctionImplementation& modelnode_is_dangly_line_865_895122c9_native();
const NativeFunctionImplementation& modelnode_is_light_line_867_d6b188e4_native();
const NativeFunctionImplementation& modelnode_is_saber_line_869_72a287f1_native();
const NativeFunctionImplementation& modelnode_is_emitter_line_871_65c50406_native();
const NativeFunctionImplementation& modelnode_is_reference_line_873_95986679_native();
const NativeFunctionImplementation& modelnode_is_aabb_line_875_65efb8e0_native();
const NativeFunctionImplementation& modelnode_is_dummy_line_877_b7087822_native();
const NativeFunctionImplementation& modelnode_texture_clean_line_881_50118ff6_native();
const NativeFunctionImplementation& modelnode_type_label_line_895_1a0757ed_native();
const NativeFunctionImplementation& resolvedanimationslot_found_line_1377_b2bb6dd4_native();
const NativeFunctionImplementation& kotormodel_nodes_line_1417_359eea1e_native();
const NativeFunctionImplementation& characterscene_is_empty_line_1998_6546bb91_native();
const NativeFunctionImplementation& characterscene_all_models_line_2003_6f8cd0df_native();
const NativeFunctionImplementation& characterscene_head_model_line_2012_c7bb6aa8_native();
const NativeFunctionImplementation& characterscene_body_model_line_2016_061967db_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::geometry
