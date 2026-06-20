#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::sceneinformation {

#ifndef GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& axismode_label_line_25_7f940ea5_native();
const NativeFunctionImplementation& kmaxscene_display_name_line_43_4c4f5179_native();
const NativeFunctionImplementation& moduleroomplacement_group_id_line_26_2739f71f_native();
const NativeFunctionImplementation& pivotdata_position_line_54_fa472186_native();
const NativeFunctionImplementation& pivotdata_rotation_line_62_8f4a7cea_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::sceneinformation
