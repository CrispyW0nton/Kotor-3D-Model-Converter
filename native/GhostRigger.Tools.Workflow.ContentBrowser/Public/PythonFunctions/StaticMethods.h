#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::contentbrowser {

#ifndef GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& resourceloadingmixin_module_group_anchor_lyt_position_line_634_d4352bba_native();
const NativeFunctionImplementation& resourceloadingmixin_runtime_model_child_count_line_727_2f2b8208_native();
const NativeFunctionImplementation& resourceloadingmixin_model_bounds_center_line_738_b02c98be_native();
const NativeFunctionImplementation& resourceloadingmixin_supports_animation_retarget_target_line_946_75ffa719_native();
const NativeFunctionImplementation& resourceloadingmixin_derive_wok_resrefs_line_971_d2ba6539_native();
const NativeFunctionImplementation& gamelibrary_detect_game_tag_line_815_80fc5b7b_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::contentbrowser
