#pragma once

#include <cstddef>

namespace ghostrigger::core::rendering {

#ifndef GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& renderergeometrymixin_compute_area_weighted_normals_line_34_34b1d19f_native();
const NativeFunctionImplementation& renderergeometrymixin_bas_attachment_root_for_node_line_240_91df42e7_native();
const NativeFunctionImplementation& renderergeometrymixin_apply_vertex_transform_line_354_5892625e_native();
const NativeFunctionImplementation& rendereroverlaymixin_hud_text_width_line_1012_45510b60_native();
const NativeFunctionImplementation& renderersetupmixin_blend_rgb_line_232_2fef0bfa_native();
const NativeFunctionImplementation& renderersetupmixin_relative_luma_line_237_44f84aac_native();
const NativeFunctionImplementation& renderersetupmixin_compute_skin_proxy_ids_line_433_5a02960f_native();
const NativeFunctionImplementation& texturecache_copy_texture_attrs_line_459_0700afca_native();
const NativeFunctionImplementation& texturecache_apply_kotor_alpha_line_469_b587da27_native();
const NativeFunctionImplementation& renderersettings_apply_defaults_line_152_cad434f7_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::rendering
