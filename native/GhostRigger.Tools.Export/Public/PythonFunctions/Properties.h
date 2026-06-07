#pragma once

#include <cstddef>

namespace ghostrigger::tools::export_ {

#ifndef GHOSTRIGGER_TOOLS_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& characterexportpreflightresult_export_allowed_line_112_99f50905_native();
const NativeFunctionImplementation& characterbuilderexporttransactionresult_succeeded_line_82_551814e9_native();
const NativeFunctionImplementation& characterbuilderexporttransactionresult_mdl_path_line_86_18384d89_native();
const NativeFunctionImplementation& characterbuilderexporttransactionresult_mdx_path_line_90_f2c3ffcd_native();
const NativeFunctionImplementation& characterbuilderexporttransactionresult_validation_report_json_path_line_94_9bb14de4_native();
const NativeFunctionImplementation& characterbuilderexporttransactionresult_validation_report_txt_path_line_98_940918be_native();
const NativeFunctionImplementation& exportjobresult_succeeded_line_104_a5b01fae_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::export_
