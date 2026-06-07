#pragma once

#include <cstddef>

namespace ghostrigger::retargeting {

#ifndef GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& basisconversion_change_of_basis_line_37_338000fa_native();
const NativeFunctionImplementation& mixamosourceadapterresult_mapped_line_90_8f9062d9_native();
const NativeFunctionImplementation& mixamosourceadapterresult_ignored_line_94_eae179fa_native();
const NativeFunctionImplementation& mixamosourceadapterresult_unmapped_line_98_ce2da706_native();
const NativeFunctionImplementation& retargetcalibrationreport_success_line_68_e1910ba5_native();
const NativeFunctionImplementation& retargetframeaudit_success_line_55_37382967_native();
const NativeFunctionImplementation& retargetpreviewaudit_passed_line_77_4eaea28d_native();
const NativeFunctionImplementation& sourceskeletonclip_node_names_line_181_6364f90b_native();
const NativeFunctionImplementation& targetskeletonaudit_success_line_38_fe34433d_native();
const NativeFunctionImplementation& ue5sourceadapterresult_mapped_line_71_45bfdd64_native();
const NativeFunctionImplementation& ue5sourceadapterresult_dropped_line_75_4d9b2022_native();
const NativeFunctionImplementation& ue5sourceadapterresult_collapsed_line_79_a1e2431e_native();
const NativeFunctionImplementation& ue5sourceadapterresult_unmapped_line_83_dd059e0b_native();
const NativeFunctionImplementation& unrealtargetskeleton_node_names_line_47_f38e0b2a_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::retargeting
