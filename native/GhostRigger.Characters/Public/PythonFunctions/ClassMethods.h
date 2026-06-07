#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_characters {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_characters_character_autofit_report_autofitoverride_from_mapping_line_72_b939c173_descriptor_json();
const char* src_core_characters_creature_appearance_creatureassembly_from_models_line_1193_dfce9043_descriptor_json();
const char* src_core_characters_creature_appearance_creatureassembly_from_resrefs_line_1260_9de5d9fa_descriptor_json();
const char* src_core_characters_native_skeleton_nativenodesnapshot_from_dict_line_77_23599e67_descriptor_json();
const char* src_core_characters_native_skeleton_nativeskeletonsnapshot_from_dict_line_107_3c42a345_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_characters
