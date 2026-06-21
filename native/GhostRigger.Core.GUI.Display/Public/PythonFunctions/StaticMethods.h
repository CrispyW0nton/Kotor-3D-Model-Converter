#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::display::shell::main {

#ifndef GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WINDOWS_MAINWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& animationworkflowmixin_is_head_animation_slot_line_278_daa495fc_native();
const NativeFunctionImplementation& resourceloadingmixin_module_group_anchor_lyt_position_line_634_d4352bba_native();
const NativeFunctionImplementation& resourceloadingmixin_runtime_model_child_count_line_727_2f2b8208_native();
const NativeFunctionImplementation& resourceloadingmixin_model_bounds_center_line_738_b02c98be_native();
const NativeFunctionImplementation& resourceloadingmixin_supports_animation_retarget_target_line_946_75ffa719_native();
const NativeFunctionImplementation& resourceloadingmixin_derive_wok_resrefs_line_971_d2ba6539_native();
const NativeFunctionImplementation& sceneworkflowmixin_sprite_node_key_line_629_f8d350f8_native();
const NativeFunctionImplementation& sceneworkflowmixin_sprite_material_payload_line_637_e3e1dbdd_native();
const NativeFunctionImplementation& sceneworkflowmixin_apply_sprite_material_payload_line_655_f8a0ee48_native();
const NativeFunctionImplementation& sceneworkflowmixin_sprite_node_has_explicit_override_line_677_a4437a56_native();
const NativeFunctionImplementation& windowchromemixin_height_for_wrapping_widget_line_693_2983b020_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::display::shell::main
