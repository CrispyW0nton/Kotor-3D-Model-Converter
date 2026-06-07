#pragma once

#include <cstddef>

namespace ghostrigger::tools::spritematerials {

#ifndef GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& decompress_dxt1_bytes_e_line_133_74538bab_native();
const NativeFunctionImplementation& decompress_dxt5_bytes_e_line_174_a7bf9284_native();
const NativeFunctionImplementation& load_tpc_bytes_legacy_inner_flip_line_496_adeeec2f_native();
const NativeFunctionImplementation& extract_txi_from_tpc_legacy_mip_sz_fn_line_663_34fe55e0_native();
const NativeFunctionImplementation& extract_txi_from_tpc_legacy_mip_sz_fn_line_691_bc8f9005_native();
const NativeFunctionImplementation& extract_txi_from_tpc_legacy_mip_sz_fn_line_697_9c5bbaff_native();
const NativeFunctionImplementation& decompress_dxt1_bytes_e_line_164_7b595deb_native();
const NativeFunctionImplementation& decompress_dxt5_bytes_e_line_202_27725da1_native();
const NativeFunctionImplementation& load_tpc_bytes_flip_line_318_544aafa3_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::spritematerials
