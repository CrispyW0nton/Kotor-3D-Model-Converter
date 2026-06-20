#pragma once

#include <cstddef>

namespace ghostrigger::core::templates {

#ifndef GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& get_bones_for_version_line_325_8ee48708_native();
const NativeFunctionImplementation& get_anim_slots_for_version_line_332_c7281819_native();
const NativeFunctionImplementation& build_humanoid_template_line_339_bbc0530a_native();
const NativeFunctionImplementation& add_placeholder_body_line_430_15dfa9e7_native();
const NativeFunctionImplementation& save_template_manifest_line_473_0baef5db_native();
const NativeFunctionImplementation& validate_animations_via_pykotor_line_521_9e959283_native();
const NativeFunctionImplementation& check_model_eyeball_nodes_line_660_29303138_native();
const NativeFunctionImplementation& split_2da_line_line_345_e1fcb025_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::templates
