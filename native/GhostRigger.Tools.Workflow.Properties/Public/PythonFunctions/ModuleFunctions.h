#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::properties {

#ifndef GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& module_from_input_line_119_11ee3249_native();
const NativeFunctionImplementation& git_from_input_line_123_7d1b755f_native();
const NativeFunctionImplementation& git_raw_line_128_8526b7f8_native();
const NativeFunctionImplementation& field_type_line_133_09abfa8f_native();
const NativeFunctionImplementation& coerce_value_line_147_07961272_native();
const NativeFunctionImplementation& raw_list_line_159_1f905db2_native();
const NativeFunctionImplementation& dataclass_items_line_167_cc0521e0_native();
const NativeFunctionImplementation& get_value_line_174_01259d2d_native();
const NativeFunctionImplementation& as_float_line_181_72f335b6_native();
const NativeFunctionImplementation& object_position_line_188_fc593ffd_native();
const NativeFunctionImplementation& object_bearing_line_197_369d0c5b_native();
const NativeFunctionImplementation& object_template_line_201_38168292_native();
const NativeFunctionImplementation& object_tag_line_205_efba54dc_native();
const NativeFunctionImplementation& dataclass_to_raw_line_209_ae3b751c_native();
const NativeFunctionImplementation& field_sort_key_line_225_d36ee55f_native();
const NativeFunctionImplementation& form_fields_line_248_b4087386_native();
const NativeFunctionImplementation& template_index_line_266_62dbf7c3_native();
const NativeFunctionImplementation& template_source_line_279_5f7ff19f_native();
const NativeFunctionImplementation& make_form_line_284_943b366c_native();
const NativeFunctionImplementation& transition_forms_line_310_f6bb69da_native();
const NativeFunctionImplementation& build_module_object_inspector_line_342_9ce4bab3_native();
const NativeFunctionImplementation& find_form_line_399_a31f82bf_native();
const NativeFunctionImplementation& apply_object_form_edit_line_406_3e1234b8_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::properties
