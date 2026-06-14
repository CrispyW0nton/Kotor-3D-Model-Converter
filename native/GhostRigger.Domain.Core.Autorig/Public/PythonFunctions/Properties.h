#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::autorig {

#ifndef GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& bonemask_masked_bones_line_449_93e3b08c_native();
const NativeFunctionImplementation& rigtemplate_bone_names_line_200_c6130ec1_native();
const NativeFunctionImplementation& clothrigconfig_pin_mdl_line_119_9ea858a9_native();
const NativeFunctionImplementation& clothrigconfig_free_mdl_line_124_18b4397d_native();
const NativeFunctionImplementation& retargetengine_stage_line_618_11405e42_native();
const NativeFunctionImplementation& retargetengine_working_model_line_622_fd6f944a_native();
const NativeFunctionImplementation& retargetengine_reference_model_line_626_13816cbc_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::autorig
