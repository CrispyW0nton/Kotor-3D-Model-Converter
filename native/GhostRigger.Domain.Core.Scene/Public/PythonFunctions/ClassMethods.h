#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::scene {

#ifndef GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& axismode_from_value_line_29_43c38e4a_native();
const NativeFunctionImplementation& kmaxscene_new_line_88_dda5f867_native();
const NativeFunctionImplementation& kmaxserializer_save_line_18_50cd4b7f_native();
const NativeFunctionImplementation& kmaxserializer_load_line_29_1667a6b4_native();
const NativeFunctionImplementation& kmaxserializer_to_dict_line_38_98bc0510_native();
const NativeFunctionImplementation& kmaxserializer_from_dict_line_65_c917e9b7_native();
const NativeFunctionImplementation& kmaxserializer_legacy_asset_objects_line_95_9c35044d_native();
const NativeFunctionImplementation& areproperties_from_are_data_line_352_f3e0928c_native();
const NativeFunctionImplementation& transform_from_dict_line_35_68aeedb9_native();
const NativeFunctionImplementation& pivotdata_from_dict_line_88_6fd6a9f3_native();
const NativeFunctionImplementation& sceneobjectinstance_from_dict_line_49_531c3383_native();
const NativeFunctionImplementation& sceneresourceref_from_dict_line_38_88675c01_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::scene
