#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::animation {

#ifndef GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& supermodelresolver_configure_line_82_459ed917_native();
const NativeFunctionImplementation& supermodelresolver_clear_cache_line_90_c728b5dd_native();
const NativeFunctionImplementation& supermodelresolver_prime_cache_line_95_33fc357d_native();
const NativeFunctionImplementation& supermodelresolver_cache_game_key_line_100_303a5917_native();
const NativeFunctionImplementation& supermodelresolver_is_null_ref_line_113_a62f019d_native();
const NativeFunctionImplementation& supermodelresolver_load_supermodel_line_119_5f17088c_native();
const NativeFunctionImplementation& supermodelresolver_resolve_animation_line_165_2e13983f_native();
const NativeFunctionImplementation& supermodelresolver_list_all_animations_line_225_a894df0f_native();
const NativeFunctionImplementation& supermodelresolver_animation_source_type_line_269_e16b380b_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::animation
