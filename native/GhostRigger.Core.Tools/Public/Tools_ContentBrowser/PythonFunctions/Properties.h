#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::contentbrowser {

#ifndef GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gameresourcerecord_resref_line_116_78f26074_native();
const NativeFunctionImplementation& gameresourcerecord_restype_line_120_f9721240_native();
const NativeFunctionImplementation& gameresourcerecord_layer_line_124_0ae162e6_native();
const NativeFunctionImplementation& gameresourcerecord_key_line_128_428e6e30_native();
const NativeFunctionImplementation& gameresourceresult_address_line_147_2c9f2ffa_native();
const NativeFunctionImplementation& resourceentry_is_model_line_148_ac3a3c87_native();
const NativeFunctionImplementation& resourceentry_is_texture_line_158_81a9e006_native();
const NativeFunctionImplementation& resourceentry_ext_line_176_f6cc4a92_native();
const NativeFunctionImplementation& resourceentry_filename_line_183_3ce7f046_native();
const NativeFunctionImplementation& modellibraryentry_display_label_line_564_2f8cb0ec_native();
const NativeFunctionImplementation& modellibraryentry_display_label_rich_line_572_c2c9f684_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::contentbrowser
