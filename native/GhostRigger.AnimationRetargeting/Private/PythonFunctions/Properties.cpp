#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_animationretargeting {

const char* src_core_animation_retargeting_retargeter_bonemappingreport_matched_count_line_55_342fb885_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.AnimationRetargeting","python_module":"src.core.animation_retargeting.retargeter","python_file":"src/core/animation_retargeting/retargeter.py","qualname":"BoneMappingReport.matched_count","name":"matched_count","kind":"properties","line":55,"end_line":56,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/animation_retargeting/retargeter.py", "BoneMappingReport.matched_count", "properties", &src_core_animation_retargeting_retargeter_bonemappingreport_matched_count_line_55_342fb885_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_animationretargeting
