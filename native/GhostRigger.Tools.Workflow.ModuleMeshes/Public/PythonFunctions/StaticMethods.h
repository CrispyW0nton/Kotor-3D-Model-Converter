#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::modulemeshes {

#ifndef GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_MODULEMESHES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& kmapvalidator_valid_transform_line_123_f2f62e68_native();
const NativeFunctionImplementation& levelexportbridge_single_export_model_line_106_74e418b1_native();
const NativeFunctionImplementation& moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_native();
const NativeFunctionImplementation& walkmeshwriter_roundtrip_line_568_cd29482e_native();
const NativeFunctionImplementation& walkmeshwriter_compute_adjacency_line_631_816fefe7_native();
const NativeFunctionImplementation& walkmeshwriter_pack_line_665_044477c6_native();
const NativeFunctionImplementation& moduleeditorpropertiespanel_set_vector_line_85_4910d35b_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::modulemeshes
