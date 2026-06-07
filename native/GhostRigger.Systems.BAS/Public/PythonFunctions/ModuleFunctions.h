#pragma once

#include <cstddef>

namespace ghostrigger::systems::bas {

#ifndef GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& normalize_bas_resref_line_25_63472742_native();
const NativeFunctionImplementation& normalize_bas_transform_line_34_2867dcbd_native();
const NativeFunctionImplementation& default_bas_attachment_transform_line_55_2f890e53_native();
const NativeFunctionImplementation& normalize_bas_model_resref_line_23_86f0d7ea_native();
const NativeFunctionImplementation& resolve_bas_head_resref_line_53_eb599759_native();
const NativeFunctionImplementation& looks_like_resref_line_117_4f528da4_native();
const NativeFunctionImplementation& dedupe_line_126_3e37b23d_native();
const NativeFunctionImplementation& model_exists_line_137_cff72b3c_native();
const NativeFunctionImplementation& resolve_head_from_appearance_tables_line_160_7c6277c5_native();
const NativeFunctionImplementation& body_name_head_candidates_line_194_0bf8d8d4_native();
const NativeFunctionImplementation& default_bas_models_dir_line_38_472c515c_native();
const NativeFunctionImplementation& safe_bas_recipe_stem_line_42_3b448488_native();
const NativeFunctionImplementation& bas_model_identity_line_49_6dedf178_native();
const NativeFunctionImplementation& build_bas_model_recipe_line_63_313e3e68_native();
const NativeFunctionImplementation& save_bas_model_recipe_line_150_ffb1ac21_native();
const NativeFunctionImplementation& normalize_bas_layer_transform_line_159_327c4094_native();
const NativeFunctionImplementation& is_bas_model_recipe_line_179_666a474f_native();
const NativeFunctionImplementation& load_bas_model_recipe_line_183_37c726d9_native();
const NativeFunctionImplementation& reset_bas_model_node_traversal_line_19_e06bc21c_native();
const NativeFunctionImplementation& find_model_node_line_37_4ef2e04a_native();
const NativeFunctionImplementation& bas_slot_for_preview_socket_line_53_7b7e3031_native();
const NativeFunctionImplementation& bas_socket_for_slot_line_66_5f721465_native();
const NativeFunctionImplementation& tag_bas_attachment_subtree_line_71_e720aa75_native();
const NativeFunctionImplementation& apply_bas_layer_transform_line_90_4bd48a78_native();
const NativeFunctionImplementation& prepare_bas_layer_root_line_99_0cb421ed_native();
const NativeFunctionImplementation& attach_bas_item_to_preview_line_116_b831a5bd_native();
const NativeFunctionImplementation& build_bas_preview_model_line_148_e4c9e40e_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::systems::bas
