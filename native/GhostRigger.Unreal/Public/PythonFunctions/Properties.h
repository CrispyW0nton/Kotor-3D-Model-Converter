#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_unreal {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_unreal_animation_retargeting_bonemappingreport_matched_count_line_115_46b24e61_descriptor_json();
const char* src_unreal_animation_retargeting_bonemappingreport_derived_count_line_119_fce392dc_descriptor_json();
const char* src_unreal_quinn_unrealskeletonasset_bone_count_line_48_9f2efdff_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_unreal
