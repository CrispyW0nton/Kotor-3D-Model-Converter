#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::autorig {

#ifndef GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& clothconstraintpainter_generate_line_240_efff0de6_native();
const NativeFunctionImplementation& clothconstraintpainter_vertical_line_278_40ec8904_native();
const NativeFunctionImplementation& clothconstraintpainter_radial_line_311_1c700ca3_native();
const NativeFunctionImplementation& clothconstraintpainter_bone_dist_line_329_4cd44677_native();
const NativeFunctionImplementation& clothconstraintpainter_cape_gradient_line_347_2c916fc9_native();
const NativeFunctionImplementation& clothrigexporter_constraints_to_mdl_line_634_10d85b88_native();
const NativeFunctionImplementation& clothrigexporter_constraints_from_mdl_line_645_68b610a2_native();
const NativeFunctionImplementation& bonepin_from_rig_guide_line_129_145951e6_native();
const NativeFunctionImplementation& bonepin_from_dict_line_159_443dc003_native();
const NativeFunctionImplementation& vertexinfluence_from_skin_data_line_210_c98b3eea_native();
const NativeFunctionImplementation& modelorientfixer_rot_yup_to_zup_line_131_df3a320f_native();
const NativeFunctionImplementation& modelorientfixer_rot_xup_to_zup_line_137_3e355925_native();
const NativeFunctionImplementation& modelorientfixer_rot_normal_yup_to_zup_line_143_cbc52c49_native();
const NativeFunctionImplementation& modelorientfixer_rot_normal_xup_to_zup_line_149_80392f02_native();
const NativeFunctionImplementation& modelorientfixer_detect_line_156_0f510b88_native();
const NativeFunctionImplementation& scalesolver_span_line_444_e3f3ed06_native();
const NativeFunctionImplementation& meshscaler_apply_line_480_c7319569_native();
const NativeFunctionImplementation& animationretargeter_transfer_line_537_502029a0_native();
const NativeFunctionImplementation& retargetengine_height_line_664_ef4553b0_native();
const NativeFunctionImplementation& retargetengine_bone_count_line_669_82fc178b_native();
const NativeFunctionImplementation& retargetengine_mesh_count_line_676_f1f1315f_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::autorig
