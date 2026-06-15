#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::camera {

#ifndef GHOSTRIGGER_TOOLS_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ghostriggercamera_from_object_line_63_00a75f63_native();
const NativeFunctionImplementation& ghostriggercamera_from_dict_line_83_1d2e8091_native();
const NativeFunctionImplementation& rendersettings_from_dict_line_41_2f47dc1e_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::camera
