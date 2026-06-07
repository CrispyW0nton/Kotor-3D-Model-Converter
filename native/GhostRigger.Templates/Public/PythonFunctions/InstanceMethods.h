#pragma once

#include <cstddef>

namespace ghostrigger::templates {

#ifndef GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TEMPLATES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& twodarow_construct_line_34_4f00bb80_native();
const NativeFunctionImplementation& twodarow_getitem_line_43_3deb55fb_native();
const NativeFunctionImplementation& twodarow_contains_line_52_27e8026b_native();
const NativeFunctionImplementation& twodarow_get_line_55_f1b27c9c_native();
const NativeFunctionImplementation& twodarow_as_dict_line_59_443468d9_native();
const NativeFunctionImplementation& twodarow_repr_line_63_e0ba0154_native();
const NativeFunctionImplementation& twoda_construct_line_80_51280743_native();
const NativeFunctionImplementation& twoda_len_line_241_01c7db26_native();
const NativeFunctionImplementation& twoda_iter_line_244_b3ebed03_native();
const NativeFunctionImplementation& twoda_getitem_line_248_e9805510_native();
const NativeFunctionImplementation& twoda_get_line_251_b2abdf65_native();
const NativeFunctionImplementation& twoda_get_int_line_263_b13fd544_native();
const NativeFunctionImplementation& twoda_get_float_line_271_7978e939_native();
const NativeFunctionImplementation& twoda_col_index_line_279_1c96b70f_native();
const NativeFunctionImplementation& twoda_find_line_287_9c8c098d_native();
const NativeFunctionImplementation& twoda_find_first_line_302_066407ce_native();
const NativeFunctionImplementation& twoda_column_values_line_307_8c2c2599_native();
const NativeFunctionImplementation& twoda_to_tsv_line_317_e35792ea_native();
const NativeFunctionImplementation& twoda_to_ascii_2da_line_325_08da05a0_native();
const NativeFunctionImplementation& twoda_repr_line_336_67e37638_native();
const NativeFunctionImplementation& twodacache_construct_line_387_020aea30_native();
const NativeFunctionImplementation& twodacache_set_library_line_391_ef421473_native();
const NativeFunctionImplementation& twodacache_get_line_395_f4262f50_native();
const NativeFunctionImplementation& twodacache_fetch_raw_line_413_8f2f66d9_native();
const NativeFunctionImplementation& twodacache_list_all_line_442_889d365e_native();
const NativeFunctionImplementation& twodacache_preload_all_line_454_7db2e0f7_native();
const NativeFunctionImplementation& twodacache_clear_line_465_abb270d0_native();
const NativeFunctionImplementation& twodacache_repr_line_468_69a81d85_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::templates
