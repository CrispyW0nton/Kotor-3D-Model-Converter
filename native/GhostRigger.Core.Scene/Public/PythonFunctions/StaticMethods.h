#pragma once

#include <cstddef>

namespace ghostrigger::core::scene {

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

const NativeFunctionImplementation& kmaxscene_asset_payload_line_61_75cc6148_native();
const NativeFunctionImplementation& kmaxscenemanager_normalize_camera_type_line_394_205df1f2_native();
const NativeFunctionImplementation& kmaxscenemanager_normalize_light_type_line_411_0362e990_native();
const NativeFunctionImplementation& kmaxscenemanager_camera_payload_line_416_dc4ef080_native();
const NativeFunctionImplementation& kmaxscenemanager_light_payload_line_425_1f04dbe5_native();
const NativeFunctionImplementation& kmaxserializer_validate_line_138_ebaba754_native();
const NativeFunctionImplementation& kmaxserializer_migrate_line_142_d4105a22_native();
const NativeFunctionImplementation& kmaxvalidator_validate_line_28_448519b7_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::scene
