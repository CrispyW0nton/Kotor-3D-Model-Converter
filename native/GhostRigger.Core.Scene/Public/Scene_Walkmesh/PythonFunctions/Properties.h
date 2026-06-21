#pragma once

#include <cstddef>

namespace ghostrigger::core::walkmesh {

#ifndef GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& walkmeshface_color_line_151_366a94f0_native();
const NativeFunctionImplementation& walkmeshface_normal_line_155_2b51a16b_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_visible_line_753_0e217618_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_key_line_814_e16bcb57_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_overlay_count_line_819_771599f7_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::walkmesh
