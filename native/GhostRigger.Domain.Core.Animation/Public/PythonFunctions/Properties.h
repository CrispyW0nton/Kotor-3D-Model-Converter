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

const NativeFunctionImplementation& animationengine_current_animation_line_723_88f811ab_native();
const NativeFunctionImplementation& animationengine_is_playing_line_727_e5083a0f_native();
const NativeFunctionImplementation& animationengine_current_time_line_731_855c8502_native();
const NativeFunctionImplementation& danglysimulator_num_free_vertices_line_2146_19ba6b23_native();
const NativeFunctionImplementation& danglysimulator_num_pinned_vertices_line_2151_d92c35d6_native();
const NativeFunctionImplementation& animstatemachine_current_state_name_line_2447_1507cbb8_native();
const NativeFunctionImplementation& animstatemachine_previous_state_name_line_2452_4a1f55f6_native();
const NativeFunctionImplementation& animstatemachine_is_running_line_2457_5f5aa3b4_native();
const NativeFunctionImplementation& animstatemachine_state_names_line_2461_e4e92a4d_native();
const NativeFunctionImplementation& animationentry_display_name_line_76_1d16f456_native();
const NativeFunctionImplementation& animationentry_fps_estimate_line_80_579d268d_native();
const NativeFunctionImplementation& animationlibrary_stats_line_271_a4dd43f9_native();
const NativeFunctionImplementation& matrixpaletteuploader_bone_count_line_1303_7e088645_native();
const NativeFunctionImplementation& matrixpaletteuploader_palette_line_1307_cff75296_native();
const NativeFunctionImplementation& tbnresult_vertex_count_line_1375_ca0235eb_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::animation
