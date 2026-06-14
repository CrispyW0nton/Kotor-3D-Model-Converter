#pragma once

#include <cstddef>

namespace ghostrigger::adapters::qt::autorig {

#ifndef GHOSTRIGGER_ADAPTERS_QTAUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_QTAUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_QTAUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qt_application_running_line_10_869101bf_native();
const NativeFunctionImplementation& run_cloth_preset_dialog_line_20_6033aef6_native();
const NativeFunctionImplementation& confirm_cloth_action_line_48_c9074cd3_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::qt::autorig
