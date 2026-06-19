#pragma once

#include <cstddef>

namespace ghostrigger::core::retargeting {

#ifndef GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& auroraanimationwriter_validate_export_motion_amplitude_line_747_c09f7fed_native();
const NativeFunctionImplementation& auroraanimationwriter_source_world_rotation_amplitude_degrees_line_796_4382d513_native();
const NativeFunctionImplementation& auroraanimationwriter_export_orientation_amplitude_degrees_line_805_5f8de857_native();
const NativeFunctionImplementation& auroraanimationwriter_hemisphere_continuous_xyzw_line_1099_fb94c156_native();
const NativeFunctionImplementation& auroraanimationwriter_constant_orientation_values_line_1111_7ff6d28f_native();
const NativeFunctionImplementation& auroraanimationwriter_position_values_from_frames_line_1133_1d0e9e8a_native();
const NativeFunctionImplementation& quaternion_from_xyzw_line_28_290fd502_native();
const NativeFunctionImplementation& transform_from_matrix_line_109_7fa18a91_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::retargeting
