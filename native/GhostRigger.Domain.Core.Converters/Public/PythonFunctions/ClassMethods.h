#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::converters {

#ifndef GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& objexporter_is_facial_geometry_line_535_594fa6cf_native();
const NativeFunctionImplementation& objexporter_is_deformation_helper_line_574_cc6f545f_native();
const NativeFunctionImplementation& objexporter_is_renderable_line_623_01a547cf_native();
const NativeFunctionImplementation& txibuilder_normal_map_preset_line_134_faf7d193_native();
const NativeFunctionImplementation& txibuilder_envmap_preset_line_142_f3d3c78b_native();
const NativeFunctionImplementation& txibuilder_diffuse_preset_line_147_1291f1af_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::converters
