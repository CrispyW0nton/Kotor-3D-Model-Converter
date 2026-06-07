#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_export {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_characters_character_export_preflight_characterexportpreflightresult_export_allowed_line_112_99f50905_descriptor_json();
const char* src_core_characters_character_export_transaction_characterbuilderexporttransactionresult_succeeded_line_82_551814e9_descriptor_json();
const char* src_core_characters_character_export_transaction_characterbuilderexporttransactionresult_mdl_path_line_86_18384d89_descriptor_json();
const char* src_core_characters_character_export_transaction_characterbuilderexporttransactionresult_mdx_path_line_90_f2c3ffcd_descriptor_json();
const char* src_core_characters_character_export_transaction_characterbuilderexporttransactionresult_validation_report_json_path_line_94_9bb14de4_descriptor_json();
const char* src_core_characters_character_export_transaction_characterbuilderexporttransactionresult_validation_report_txt_path_line_98_940918be_descriptor_json();
const char* src_core_export_export_job_exportjobresult_succeeded_line_104_a5b01fae_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_export
