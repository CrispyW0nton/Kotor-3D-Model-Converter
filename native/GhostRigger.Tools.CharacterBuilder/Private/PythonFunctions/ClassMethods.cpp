#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_characterbuilder {

const char* src_core_characters_character_autofit_report_autofitoverride_from_mapping_line_72_b939c173_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.CharacterBuilder","python_module":"src.core.characters.character_autofit_report","python_file":"src/core/characters/character_autofit_report.py","qualname":"AutoFitOverride.from_mapping","name":"from_mapping","kind":"class_methods","line":72,"end_line":81,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_characters_creature_appearance_creatureassembly_from_models_line_1193_dfce9043_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.CharacterBuilder","python_module":"src.core.characters.creature_appearance","python_file":"src/core/characters/creature_appearance.py","qualname":"CreatureAssembly.from_models","name":"from_models","kind":"class_methods","line":1193,"end_line":1257,"signature":{"args":["cls","body_model","head_model","game"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_characters_creature_appearance_creatureassembly_from_resrefs_line_1260_9de5d9fa_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.CharacterBuilder","python_module":"src.core.characters.creature_appearance","python_file":"src/core/characters/creature_appearance.py","qualname":"CreatureAssembly.from_resrefs","name":"from_resrefs","kind":"class_methods","line":1260,"end_line":1312,"signature":{"args":["cls","body_resref","head_resref","resource_manager","game"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_characters_native_skeleton_nativenodesnapshot_from_dict_line_77_23599e67_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.CharacterBuilder","python_module":"src.core.characters.native_skeleton","python_file":"src/core/characters/native_skeleton.py","qualname":"NativeNodeSnapshot.from_dict","name":"from_dict","kind":"class_methods","line":77,"end_line":82,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_characters_native_skeleton_nativeskeletonsnapshot_from_dict_line_107_3c42a345_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.CharacterBuilder","python_module":"src.core.characters.native_skeleton","python_file":"src/core/characters/native_skeleton.py","qualname":"NativeSkeletonSnapshot.from_dict","name":"from_dict","kind":"class_methods","line":107,"end_line":114,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/characters/character_autofit_report.py", "AutoFitOverride.from_mapping", "class_methods", &src_core_characters_character_autofit_report_autofitoverride_from_mapping_line_72_b939c173_descriptor_json},
        {"src/core/characters/creature_appearance.py", "CreatureAssembly.from_models", "class_methods", &src_core_characters_creature_appearance_creatureassembly_from_models_line_1193_dfce9043_descriptor_json},
        {"src/core/characters/creature_appearance.py", "CreatureAssembly.from_resrefs", "class_methods", &src_core_characters_creature_appearance_creatureassembly_from_resrefs_line_1260_9de5d9fa_descriptor_json},
        {"src/core/characters/native_skeleton.py", "NativeNodeSnapshot.from_dict", "class_methods", &src_core_characters_native_skeleton_nativenodesnapshot_from_dict_line_77_23599e67_descriptor_json},
        {"src/core/characters/native_skeleton.py", "NativeSkeletonSnapshot.from_dict", "class_methods", &src_core_characters_native_skeleton_nativeskeletonsnapshot_from_dict_line_107_3c42a345_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_characterbuilder
