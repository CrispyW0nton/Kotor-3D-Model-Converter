#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_unreal {

const char* src_unreal_animation_retargeting_bonemappingreport_matched_count_line_115_46b24e61_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Unreal","python_module":"src.unreal.animation_retargeting","python_file":"src/unreal/animation_retargeting.py","qualname":"BoneMappingReport.matched_count","name":"matched_count","kind":"properties","line":115,"end_line":116,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_unreal_animation_retargeting_bonemappingreport_derived_count_line_119_fce392dc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Unreal","python_module":"src.unreal.animation_retargeting","python_file":"src/unreal/animation_retargeting.py","qualname":"BoneMappingReport.derived_count","name":"derived_count","kind":"properties","line":119,"end_line":120,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_unreal_quinn_unrealskeletonasset_bone_count_line_48_9f2efdff_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Unreal","python_module":"src.unreal.quinn","python_file":"src/unreal/quinn.py","qualname":"UnrealSkeletonAsset.bone_count","name":"bone_count","kind":"properties","line":48,"end_line":49,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/unreal/animation_retargeting.py", "BoneMappingReport.matched_count", "properties", &src_unreal_animation_retargeting_bonemappingreport_matched_count_line_115_46b24e61_descriptor_json},
        {"src/unreal/animation_retargeting.py", "BoneMappingReport.derived_count", "properties", &src_unreal_animation_retargeting_bonemappingreport_derived_count_line_119_fce392dc_descriptor_json},
        {"src/unreal/quinn.py", "UnrealSkeletonAsset.bone_count", "properties", &src_unreal_quinn_unrealskeletonasset_bone_count_line_48_9f2efdff_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_unreal
