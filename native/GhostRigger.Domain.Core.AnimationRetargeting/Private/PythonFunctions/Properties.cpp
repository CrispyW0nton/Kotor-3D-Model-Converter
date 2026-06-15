#include "PythonFunctions/Properties.h"

namespace ghostrigger::domain::core::animationretargeting {

const NativeFunctionImplementation& bonemappingreport_matched_count_line_55_342fb885_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.AnimationRetargeting",
        "ghostrigger::domain::core::animationretargeting::core::animation_retargeting::retargeter",
        "src/core/animation_retargeting/retargeter.py",
        "BoneMappingReport.matched_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.AnimationRetargeting","namespace":"ghostrigger::domain::core::animationretargeting::core::animation_retargeting::retargeter","python_file":"src/core/animation_retargeting/retargeter.py","qualname":"BoneMappingReport.matched_count","name":"matched_count","callable_type":"properties","line":55,"end_line":56,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        bonemappingreport_matched_count_line_55_342fb885_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::animationretargeting
