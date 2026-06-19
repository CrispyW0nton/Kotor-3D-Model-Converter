#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::rendering {

const NativeFunctionImplementation& project_vertices_np_line_86_3ca949f7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "project_vertices_np",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"project_vertices_np","name":"project_vertices_np","callable_type":"module_functions","line":86,"end_line":110,"signature":{"args":["vx","vy","vz","W","H","f"],"positional_count":6,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& frustum_cull_np_line_113_9bccb4dd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "frustum_cull_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"frustum_cull_np","name":"frustum_cull_np","callable_type":"module_functions","line":113,"end_line":133,"signature":{"args":["sx","sy","W","H"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& depth_sort_np_line_136_478fd4c3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "depth_sort_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"depth_sort_np","name":"depth_sort_np","callable_type":"module_functions","line":136,"end_line":148,"signature":{"args":["depths"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fconstructe_uv_filter_np_line_151_d7d62dcc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "finite_uv_filter_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"finite_uv_filter_np","name":"finite_uv_filter_np","callable_type":"module_functions","line":151,"end_line":162,"signature":{"args":["uvs"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& shade_colors_np_line_165_dd196f7d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "shade_colors_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"shade_colors_np","name":"shade_colors_np","callable_type":"module_functions","line":165,"end_line":188,"signature":{"args":["normals","light_dir","light_dir2","ambient","diffuse_rgb"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_triangle_numpy_line_195_4e1c8ac8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "_rasterize_triangle_numpy",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"_rasterize_triangle_numpy","name":"_rasterize_triangle_numpy","callable_type":"module_functions","line":195,"end_line":299,"signature":{"args":["buf","tex","x0","y0","x1","y1","x2","y2","u0","v0","u1","v1","u2","v2","shade_r","shade_g","shade_b","node_alpha","clamp_s","clamp_t"],"positional_count":20,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_triangle_jit_line_308_297096d2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "_rasterize_triangle_jit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"_rasterize_triangle_jit","name":"_rasterize_triangle_jit","callable_type":"module_functions","line":308,"end_line":380,"signature":{"args":["buf","tex","x0","y0","x1","y1","x2","y2","u0","v0","u1","v1","u2","v2","shade_r","shade_g","shade_b","node_alpha_i255","clamp_s","clamp_t"],"positional_count":20,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_frame_jit_line_383_c5df2ead_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "_rasterize_frame_jit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"_rasterize_frame_jit","name":"_rasterize_frame_jit","callable_type":"module_functions","line":383,"end_line":475,"signature":{"args":["buf","tex","verts_sx","verts_sy","uvs_u","uvs_v","face_v0","face_v1","face_v2","shade_r","shade_g","shade_b","node_alpha_i255","visible_mask","clamp_s","clamp_t"],"positional_count":16,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& flat_shade_frame_jit_line_478_01aa72ee_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "_flat_shade_frame_jit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"_flat_shade_frame_jit","name":"_flat_shade_frame_jit","callable_type":"module_functions","line":478,"end_line":519,"signature":{"args":["buf","verts_sx","verts_sy","face_v0","face_v1","face_v2","fill_r","fill_g","fill_b","visible_mask"],"positional_count":10,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& warmup_jit_line_526_9ee39da9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "warmup_jit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"warmup_jit","name":"warmup_jit","callable_type":"module_functions","line":526,"end_line":573,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_triangle_line_576_3f417fc3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "rasterize_triangle",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"rasterize_triangle","name":"rasterize_triangle","callable_type":"module_functions","line":576,"end_line":611,"signature":{"args":["buf","tex","x0","y0","x1","y1","x2","y2","u0","v0","u1","v1","u2","v2","shade_r","shade_g","shade_b","node_alpha","clamp_s","clamp_t"],"positional_count":20,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_frame_line_614_790112b7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "rasterize_frame",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"rasterize_frame","name":"rasterize_frame","callable_type":"module_functions","line":614,"end_line":667,"signature":{"args":["buf","tex","verts_sx","verts_sy","uvs_u","uvs_v","face_v0","face_v1","face_v2","shade_r","shade_g","shade_b","node_alpha","visible","clamp_s","clamp_t"],"positional_count":16,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& flat_shade_frame_line_670_dad8f1ae_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::accel",
        "src/core/rendering/accel.py",
        "flat_shade_frame",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::accel","python_file":"src/core/rendering/accel.py","qualname":"flat_shade_frame","name":"flat_shade_frame","callable_type":"module_functions","line":670,"end_line":719,"signature":{"args":["buf","verts_sx","verts_sy","face_v0","face_v1","face_v2","fill_r","fill_g","fill_b","visible"],"positional_count":10,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& hex_to_rgb_float_line_6_d961967c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::color_utils",
        "src/core/rendering/color_utils.py",
        "_hex_to_rgb_float",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::color_utils","python_file":"src/core/rendering/color_utils.py","qualname":"_hex_to_rgb_float","name":"_hex_to_rgb_float","callable_type":"module_functions","line":6,"end_line":17,"signature":{"args":["value","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& hex_to_rgb_tuple_line_24_2755e159_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::colors",
        "src/core/rendering/frame_core/colors.py",
        "_hex_to_rgb_tuple",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::colors","python_file":"src/core/rendering/frame_core/colors.py","qualname":"_hex_to_rgb_tuple","name":"_hex_to_rgb_tuple","callable_type":"module_functions","line":24,"end_line":31,"signature":{"args":["value","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rgb_str_to_tuple_line_34_cee92d1e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::colors",
        "src/core/rendering/frame_core/colors.py",
        "_rgb_str_to_tuple",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::colors","python_file":"src/core/rendering/frame_core/colors.py","qualname":"_rgb_str_to_tuple","name":"_rgb_str_to_tuple","callable_type":"module_functions","line":34,"end_line":36,"signature":{"args":["s"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& paste_textured_triangle_line_39_407f8a8a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::colors",
        "src/core/rendering/frame_core/colors.py",
        "_paste_textured_triangle",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::colors","python_file":"src/core/rendering/frame_core/colors.py","qualname":"_paste_textured_triangle","name":"_paste_textured_triangle","callable_type":"module_functions","line":39,"end_line":678,"signature":{"args":["img","tex_img","sp0","sp1","sp2","uv0","uv1","uv2","W","H","shade_color","sel_brightness","node_alpha","is_additive","skip_seam_fix","skip_seam_u","skip_seam_v","clamp_s","clamp_t","is_punchthrough"],"positional_count":20,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& paste_lightmap_triangle_line_681_2912f524_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::colors",
        "src/core/rendering/frame_core/colors.py",
        "_paste_lightmap_triangle",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::colors","python_file":"src/core/rendering/frame_core/colors.py","qualname":"_paste_lightmap_triangle","name":"_paste_lightmap_triangle","callable_type":"module_functions","line":681,"end_line":779,"signature":{"args":["img","lm_img","sp0","sp1","sp2","lm_uv0","lm_uv1","lm_uv2","W","H"],"positional_count":10,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& warmup_jit_line_93_0e6ef2ee_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_warmup_jit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_warmup_jit","name":"_warmup_jit","callable_type":"module_functions","line":93,"end_line":93,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_proj_verts_line_94_0b3e259f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_proj_verts",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_proj_verts","name":"_accel_proj_verts","callable_type":"module_functions","line":94,"end_line":94,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_frustum_cull_line_95_0a1d8011_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_frustum_cull",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_frustum_cull","name":"_accel_frustum_cull","callable_type":"module_functions","line":95,"end_line":95,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_depth_sort_line_96_b7ddf1bc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_depth_sort",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_depth_sort","name":"_accel_depth_sort","callable_type":"module_functions","line":96,"end_line":96,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_rasterize_frame_line_97_c1f0ed8b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_rasterize_frame",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_rasterize_frame","name":"_accel_rasterize_frame","callable_type":"module_functions","line":97,"end_line":97,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_flat_shade_frame_line_98_de274f7a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_flat_shade_frame",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_flat_shade_frame","name":"_accel_flat_shade_frame","callable_type":"module_functions","line":98,"end_line":98,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& accel_shade_colors_line_99_01acb5e5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::dependencies",
        "src/core/rendering/frame_core/dependencies.py",
        "_accel_shade_colors",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::dependencies","python_file":"src/core/rendering/frame_core/dependencies.py","qualname":"_accel_shade_colors","name":"_accel_shade_colors","callable_type":"module_functions","line":99,"end_line":99,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gr_probe_line_10_574234dd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::diagnostics",
        "src/core/rendering/frame_core/diagnostics.py",
        "_gr_probe",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::diagnostics","python_file":"src/core/rendering/frame_core/diagnostics.py","qualname":"_gr_probe","name":"_gr_probe","callable_type":"module_functions","line":10,"end_line":52,"signature":{"args":["tag","node","wp","wo","is_id"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rasterize_triangle_textured_line_13_0e54f6b1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::frame_core::rasterizer",
        "src/core/rendering/frame_core/rasterizer.py",
        "_rasterize_triangle_textured",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::frame_core::rasterizer","python_file":"src/core/rendering/frame_core/rasterizer.py","qualname":"_rasterize_triangle_textured","name":"_rasterize_triangle_textured","callable_type":"module_functions","line":13,"end_line":123,"signature":{"args":["pixels","W","H","z_buf","p0","p1","p2","uv0","uv1","uv2","n0","n1","n2","tex_img","tex_cache","light_dir","eye_dir","diffuse_color","ambient_color","specular_col","shininess","selfillum","alpha","shade_mode"],"positional_count":24,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debug_draw_table_line_42_9ec84b51_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_debug_tables",
        "src/core/rendering/gpu_debug_tables.py",
        "debug_draw_table",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_debug_tables","python_file":"src/core/rendering/gpu_debug_tables.py","qualname":"debug_draw_table","name":"debug_draw_table","callable_type":"module_functions","line":42,"end_line":92,"signature":{"args":["model","textures"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debug_uv_channel_table_line_95_a1f860e8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_debug_tables",
        "src/core/rendering/gpu_debug_tables.py",
        "debug_uv_channel_table",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_debug_tables","python_file":"src/core/rendering/gpu_debug_tables.py","qualname":"debug_uv_channel_table","name":"debug_uv_channel_table","callable_type":"module_functions","line":95,"end_line":176,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debug_texture_cache_table_line_179_01c72050_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_debug_tables",
        "src/core/rendering/gpu_debug_tables.py",
        "debug_texture_cache_table",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_debug_tables","python_file":"src/core/rendering/gpu_debug_tables.py","qualname":"debug_texture_cache_table","name":"debug_texture_cache_table","callable_type":"module_functions","line":179,"end_line":272,"signature":{"args":["model","textures"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debug_material_role_table_line_275_fb8306c6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_debug_tables",
        "src/core/rendering/gpu_debug_tables.py",
        "debug_material_role_table",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_debug_tables","python_file":"src/core/rendering/gpu_debug_tables.py","qualname":"debug_material_role_table","name":"debug_material_role_table","callable_type":"module_functions","line":275,"end_line":347,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& path_from_env_line_19_14f3c397_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_path_from_env",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_path_from_env","name":"_path_from_env","callable_type":"module_functions","line":19,"end_line":20,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& int_env_clamped_line_23_d561e4b4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_int_env_clamped",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_int_env_clamped","name":"_int_env_clamped","callable_type":"module_functions","line":23,"end_line":28,"signature":{"args":["name","minimum","maximum","default"],"positional_count":1,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gl_state_trace_path_line_31_dc7a1b70_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_gl_state_trace_path",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_gl_state_trace_path","name":"_gl_state_trace_path","callable_type":"module_functions","line":31,"end_line":32,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lm_data_dump_path_line_35_42ca528c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_lm_data_dump_path",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_lm_data_dump_path","name":"_lm_data_dump_path","callable_type":"module_functions","line":35,"end_line":36,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_dump_path_line_39_fe55d8b8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_skin_dump_path",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_skin_dump_path","name":"_skin_dump_path","callable_type":"module_functions","line":39,"end_line":40,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debug_visualize_mode_line_43_5b215ffd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_debug_visualize_mode",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_debug_visualize_mode","name":"_debug_visualize_mode","callable_type":"module_functions","line":43,"end_line":44,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lm_composite_mode_line_47_d363b831_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config",
        "src/core/rendering/gpu_diagnostics_config.py",
        "_lm_composite_mode",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_config","python_file":"src/core/rendering/gpu_diagnostics_config.py","qualname":"_lm_composite_mode","name":"_lm_composite_mode","callable_type":"module_functions","line":47,"end_line":48,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& jsonable_gl_value_line_34_1ede079b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_jsonable_gl_value",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_jsonable_gl_value","name":"_jsonable_gl_value","callable_type":"module_functions","line":34,"end_line":43,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_gl_attr_line_46_f3c09db3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_safe_gl_attr",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_safe_gl_attr","name":"_safe_gl_attr","callable_type":"module_functions","line":46,"end_line":50,"signature":{"args":["obj","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& uniform_trace_value_line_53_a664db23_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_uniform_trace_value",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_uniform_trace_value","name":"_uniform_trace_value","callable_type":"module_functions","line":53,"end_line":60,"signature":{"args":["uniforms","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_gl_state_trace_record_line_63_661c5f41_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_build_gl_state_trace_record",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_build_gl_state_trace_record","name":"_build_gl_state_trace_record","callable_type":"module_functions","line":63,"end_line":121,"signature":{"args":["ctx","prog","node","pass_name","tri_count","blend_enabled","tex_name","lm_name","env_name","spec_name","feature_mask","uniforms"],"positional_count":0,"keyword_only_count":12,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& append_gl_state_trace_line_124_86a67054_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_append_gl_state_trace",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_append_gl_state_trace","name":"_append_gl_state_trace","callable_type":"module_functions","line":124,"end_line":132,"signature":{"args":["path","record"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& first_uv_pairs_line_135_da46e2f2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_first_uv_pairs",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_first_uv_pairs","name":"_first_uv_pairs","callable_type":"module_functions","line":135,"end_line":142,"signature":{"args":["values","limit"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& first_vbo_uv_pairs_line_145_8a1604a1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_first_vbo_uv_pairs",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_first_vbo_uv_pairs","name":"_first_vbo_uv_pairs","callable_type":"module_functions","line":145,"end_line":152,"signature":{"args":["vdata","start","limit"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& texture_content_stats_line_155_f01bae93_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_texture_content_stats",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_texture_content_stats","name":"_texture_content_stats","callable_type":"module_functions","line":155,"end_line":206,"signature":{"args":["img"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmap_role_info_line_209_0ccec99b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_lightmap_role_info",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_lightmap_role_info","name":"_lightmap_role_info","callable_type":"module_functions","line":209,"end_line":245,"signature":{"args":["node","has_lm_flag","lightmap_bound"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_lm_data_dump_record_line_248_50e702ce_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_build_lm_data_dump_record",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_build_lm_data_dump_record","name":"_build_lm_data_dump_record","callable_type":"module_functions","line":248,"end_line":292,"signature":{"args":["ctx","prog","node","pass_name","gm","has_lm_flag","lightmap_bound","lm_img","lm_name","uniforms"],"positional_count":0,"keyword_only_count":10,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& append_jsonl_record_line_295_860d61fe_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_append_jsonl_record",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_append_jsonl_record","name":"_append_jsonl_record","callable_type":"module_functions","line":295,"end_line":303,"signature":{"args":["path","record","label"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix4_json_line_306_ba4cf4dd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix4_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix4_json","name":"_matrix4_json","callable_type":"module_functions","line":306,"end_line":312,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix4_inverse_json_line_315_0b488bbd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix4_inverse_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix4_inverse_json","name":"_matrix4_inverse_json","callable_type":"module_functions","line":315,"end_line":321,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix4_mul_json_line_324_613234fd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix4_mul_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix4_mul_json","name":"_matrix4_mul_json","callable_type":"module_functions","line":324,"end_line":330,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix4_det_value_line_333_10bbe3a5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix4_det_value",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix4_det_value","name":"_matrix4_det_value","callable_type":"module_functions","line":333,"end_line":339,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& uploaded_palette_array_from_uploader_line_342_fddf1b89_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_uploaded_palette_array_from_uploader",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_uploaded_palette_array_from_uploader","name":"_uploaded_palette_array_from_uploader","callable_type":"module_functions","line":342,"end_line":355,"signature":{"args":["uploader"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& homogeneous_position_json_line_358_ac991133_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_homogeneous_position_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_homogeneous_position_json","name":"_homogeneous_position_json","callable_type":"module_functions","line":358,"end_line":366,"signature":{"args":["vec"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& first_divergence_stage_line_369_c7da1b20_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_first_divergence_stage",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_first_divergence_stage","name":"_first_divergence_stage","callable_type":"module_functions","line":369,"end_line":380,"signature":{"args":["stage_pairs","tolerance"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix_max_abs_delta_line_383_59f01372_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix_max_abs_delta",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix_max_abs_delta","name":"_matrix_max_abs_delta","callable_type":"module_functions","line":383,"end_line":391,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix_translation_norm_line_394_e64780c0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix_translation_norm",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix_translation_norm","name":"_matrix_translation_norm","callable_type":"module_functions","line":394,"end_line":404,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix_rotation_only_line_407_b4c89a01_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_matrix_rotation_only",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_matrix_rotation_only","name":"_matrix_rotation_only","callable_type":"module_functions","line":407,"end_line":420,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qbone_inverse_bind_json_line_423_dc625269_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_qbone_inverse_bind_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_qbone_inverse_bind_json","name":"_qbone_inverse_bind_json","callable_type":"module_functions","line":423,"end_line":449,"signature":{"args":["node","local_idx"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qbone_direct_bind_json_line_452_87c34f93_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_qbone_direct_bind_json",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_qbone_direct_bind_json","name":"_qbone_direct_bind_json","callable_type":"module_functions","line":452,"end_line":462,"signature":{"args":["node","local_idx"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qbone_matrix_np_line_465_e2e68a5e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_qbone_matrix_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_qbone_matrix_np","name":"_qbone_matrix_np","callable_type":"module_functions","line":465,"end_line":482,"signature":{"args":["node","local_idx","order","inverse"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_world_matrix_for_pose_np_line_485_d8054911_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_node_world_matrix_for_pose_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_node_world_matrix_for_pose_np","name":"_node_world_matrix_for_pose_np","callable_type":"module_functions","line":485,"end_line":510,"signature":{"args":["node","anim_pose","cache"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_pose_chain_records_line_513_2a4aab68_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_node_pose_chain_records",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_node_pose_chain_records","name":"_node_pose_chain_records","callable_type":"module_functions","line":513,"end_line":531,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& quat_xyzw_to_mat4_np_line_534_d9a3b5ee_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_quat_xyzw_to_mat4_np",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_quat_xyzw_to_mat4_np","name":"_quat_xyzw_to_mat4_np","callable_type":"module_functions","line":534,"end_line":554,"signature":{"args":["qx","qy","qz","qw"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& xoreos_first_frame_orientation_matrix_line_557_fce39b4e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_xoreos_first_frame_orientation_matrix",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_xoreos_first_frame_orientation_matrix","name":"_xoreos_first_frame_orientation_matrix","callable_type":"module_functions","line":557,"end_line":593,"signature":{"args":["skin_node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_matrix_for_formula_line_618_9cc7f336_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_matrix_for_formula",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_matrix_for_formula","name":"_skin_3g_matrix_for_formula","callable_type":"module_functions","line":618,"end_line":663,"signature":{"args":["formula","skin_bind","animated_world","q_tr_inv","q_rt_inv","q_tr_direct","q_rt_direct","rot_only_skin_bind","xoreos_first_frame_outer"],"positional_count":9,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_role_for_bone_line_666_95ed8883_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_role_for_bone",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_role_for_bone","name":"_skin_3g_role_for_bone","callable_type":"module_functions","line":666,"end_line":676,"signature":{"args":["bone_name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_role_priority_line_679_301987b6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_role_priority",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_role_priority","name":"_skin_3g_role_priority","callable_type":"module_functions","line":679,"end_line":701,"signature":{"args":["bone_name","role"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& select_skin_3g_probe_vertices_line_704_12e70976_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_select_skin_3g_probe_vertices",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_select_skin_3g_probe_vertices","name":"_select_skin_3g_probe_vertices","callable_type":"module_functions","line":704,"end_line":729,"signature":{"args":["node","bone_map","skin_data"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_bind_equivalence_record_line_732_e3864866_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_bind_equivalence_record",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_bind_equivalence_record","name":"_skin_bind_equivalence_record","callable_type":"module_functions","line":732,"end_line":762,"signature":{"args":["node","uploader"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_candidate_records_line_765_95075d52_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_candidate_records",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_candidate_records","name":"_skin_3g_candidate_records","callable_type":"module_functions","line":765,"end_line":1230,"signature":{"args":["model","node","bone_map","skin_data","vertices","anim_pose","uploaded_palette_arr","uploaded_positions","uploaded_bone_ids","uploaded_weights","uploaded_source_indices"],"positional_count":0,"keyword_only_count":11,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_live_slot_records_line_1233_88a63431_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_live_slot_records",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_live_slot_records","name":"_skin_live_slot_records","callable_type":"module_functions","line":1233,"end_line":1333,"signature":{"args":["model","node","bone_map","skin_data","bone_remap","uploader","palette_arr","uploaded_palette_arr","anim_pose","anim_base_pose"],"positional_count":0,"keyword_only_count":10,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_skin_dump_record_line_1336_1e8ff3a1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_build_skin_dump_record",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_build_skin_dump_record","name":"_build_skin_dump_record","callable_type":"module_functions","line":1336,"end_line":1666,"signature":{"args":["model","node","pass_name","uploader","bone_remap","uniforms","gm","anim_pose","anim_base_pose","anim_time","selected_vertex"],"positional_count":0,"keyword_only_count":11,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pose_node_transform_line_1669_c2989b35_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_pose_node_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_pose_node_transform","name":"_pose_node_transform","callable_type":"module_functions","line":1669,"end_line":1684,"signature":{"args":["anim_pose","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& select_skin_probe_vertex_line_1687_bc6f7e2f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_select_skin_probe_vertex",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_select_skin_probe_vertex","name":"_select_skin_probe_vertex","callable_type":"module_functions","line":1687,"end_line":1700,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_parent_chain_names_line_1703_3065b3a0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_node_parent_chain_names",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_node_parent_chain_names","name":"_node_parent_chain_names","callable_type":"module_functions","line":1703,"end_line":1709,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_uses_single_tile_atlas_line_1712_7c035216_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_node_uses_single_tile_atlas",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_node_uses_single_tile_atlas","name":"_node_uses_single_tile_atlas","callable_type":"module_functions","line":1712,"end_line":1728,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& should_auto_clamp_diffuse_line_1731_1c306c28_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_should_auto_clamp_diffuse",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_should_auto_clamp_diffuse","name":"_should_auto_clamp_diffuse","callable_type":"module_functions","line":1731,"end_line":1741,"signature":{"args":["node","is_module"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& compute_model_bounds_line_16_cf1ab2a2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_scene_helpers",
        "src/core/rendering/gpu_scene_helpers.py",
        "_compute_model_bounds",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_compute_model_bounds","name":"_compute_model_bounds","callable_type":"module_functions","line":16,"end_line":115,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& apply_txi_from_textures_to_model_line_118_3dff2d89_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_scene_helpers",
        "src/core/rendering/gpu_scene_helpers.py",
        "_apply_txi_from_textures_to_model",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_apply_txi_from_textures_to_model","name":"_apply_txi_from_textures_to_model","callable_type":"module_functions","line":118,"end_line":194,"signature":{"args":["model","textures"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& split_vbo_attributes_for_gpu_line_21_9cff8882_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::gpu_vbo_layout",
        "src/core/rendering/gpu_vbo_layout.py",
        "_split_vbo_attributes_for_gpu",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::gpu_vbo_layout","python_file":"src/core/rendering/gpu_vbo_layout.py","qualname":"_split_vbo_attributes_for_gpu","name":"_split_vbo_attributes_for_gpu","callable_type":"module_functions","line":21,"end_line":29,"signature":{"args":["vdata"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& collect_hardware_diagnostics_line_94_5881f1f3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "collect_hardware_diagnostics",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"collect_hardware_diagnostics","name":"collect_hardware_diagnostics","callable_type":"module_functions","line":94,"end_line":124,"signature":{"args":["renderer_diagnostics","target_fps"],"positional_count":0,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cpu_name_line_127_c7716d7e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_cpu_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_cpu_name","name":"_cpu_name","callable_type":"module_functions","line":127,"end_line":151,"signature":{"args":["cpu_payload","windows_cpu"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cpu_flags_line_154_660bb9e1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_cpu_flags",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_cpu_flags","name":"_cpu_flags","callable_type":"module_functions","line":154,"end_line":159,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& physical_core_count_line_162_6f5fbb6e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_physical_core_count",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_physical_core_count","name":"_physical_core_count","callable_type":"module_functions","line":162,"end_line":172,"signature":{"args":["windows_cpu"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& logical_thread_count_line_175_01d8bc20_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_logical_thread_count",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_logical_thread_count","name":"_logical_thread_count","callable_type":"module_functions","line":175,"end_line":178,"signature":{"args":["windows_cpu"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& adapter_name_line_181_d50546a1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_adapter_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_adapter_name","name":"_adapter_name","callable_type":"module_functions","line":181,"end_line":199,"signature":{"args":["renderer_diagnostics"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cpuinfo_payload_line_203_2b37f212_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_cpuinfo_payload",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_cpuinfo_payload","name":"_cpuinfo_payload","callable_type":"module_functions","line":203,"end_line":210,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& windows_processor_info_line_214_64580fab_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_windows_processor_info",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_windows_processor_info","name":"_windows_processor_info","callable_type":"module_functions","line":214,"end_line":252,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& architecture_label_line_255_c7c480b1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_architecture_label",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_architecture_label","name":"_architecture_label","callable_type":"module_functions","line":255,"end_line":272,"signature":{"args":["cpu_payload","windows_cpu"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& windows_processor_feature_flags_line_275_9ae4f93b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_windows_processor_feature_flags",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_windows_processor_feature_flags","name":"_windows_processor_feature_flags","callable_type":"module_functions","line":275,"end_line":295,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& windows_gpu_adapter_name_line_299_16f551e4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_windows_gpu_adapter_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_windows_gpu_adapter_name","name":"_windows_gpu_adapter_name","callable_type":"module_functions","line":299,"end_line":348,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_int_line_351_3f7f77a2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::hardware_info",
        "src/core/rendering/hardware_info.py",
        "_safe_int",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::hardware_info","python_file":"src/core/rendering/hardware_info.py","qualname":"_safe_int","name":"_safe_int","callable_type":"module_functions","line":351,"end_line":355,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& iter_mesh_render_data_line_65_fa47e988_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "iter_mesh_render_data",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"iter_mesh_render_data","name":"iter_mesh_render_data","callable_type":"module_functions","line":65,"end_line":208,"signature":{"args":["model","anim_pose","anim_base_pose","textures","allow_cpu_skinning","vbo_builder"],"positional_count":1,"keyword_only_count":5,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& model_nodes_line_211_661ae3a2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_model_nodes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_model_nodes","name":"_model_nodes","callable_type":"module_functions","line":211,"end_line":222,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_is_renderable_mesh_line_225_e3ba8c3b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_node_is_renderable_mesh",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_node_is_renderable_mesh","name":"_node_is_renderable_mesh","callable_type":"module_functions","line":225,"end_line":236,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& extract_node_arrays_line_239_41751f47_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_extract_node_arrays",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_extract_node_arrays","name":"_extract_node_arrays","callable_type":"module_functions","line":239,"end_line":323,"signature":{"args":["node","anim_pose","vbo_builder"],"positional_count":1,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skinned_lbs_vbo_cache_key_line_326_3546a59b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_skinned_lbs_vbo_cache_key",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_skinned_lbs_vbo_cache_key","name":"_skinned_lbs_vbo_cache_key","callable_type":"module_functions","line":326,"end_line":343,"signature":{"args":["node","vbo_builder","apply_skin_node_transform_for_bind"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& static_vbo_cache_key_line_346_d5eafd23_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_static_vbo_cache_key",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_static_vbo_cache_key","name":"_static_vbo_cache_key","callable_type":"module_functions","line":346,"end_line":359,"signature":{"args":["node","vbo_builder"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& get_skinned_lbs_vbo_cache_line_362_d6f98c35_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_get_skinned_lbs_vbo_cache",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_get_skinned_lbs_vbo_cache","name":"_get_skinned_lbs_vbo_cache","callable_type":"module_functions","line":362,"end_line":371,"signature":{"args":["node","cache_key"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& set_skinned_lbs_vbo_cache_line_374_25580cd0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_set_skinned_lbs_vbo_cache",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_set_skinned_lbs_vbo_cache","name":"_set_skinned_lbs_vbo_cache","callable_type":"module_functions","line":374,"end_line":380,"signature":{"args":["node","cache_key","arrays"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& smooth_render_normals_line_383_3400ba22_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "smooth_render_normals",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"smooth_render_normals","name":"smooth_render_normals","callable_type":"module_functions","line":383,"end_line":437,"signature":{"args":["positions","normals","indices","crease_degrees","position_epsilon"],"positional_count":3,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& coerce_normal_array_line_440_fec0c1af_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_coerce_normal_array",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_coerce_normal_array","name":"_coerce_normal_array","callable_type":"module_functions","line":440,"end_line":457,"signature":{"args":["normals","count"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& area_weighted_normal_accum_line_460_c1f111bb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_area_weighted_normal_accum",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_area_weighted_normal_accum","name":"_area_weighted_normal_accum","callable_type":"module_functions","line":460,"end_line":484,"signature":{"args":["positions","indices"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_rows_line_487_a0d58bc1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_normalize_rows",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_normalize_rows","name":"_normalize_rows","callable_type":"module_functions","line":487,"end_line":504,"signature":{"args":["values","fallback"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& extract_skinning_line_507_5c8210f3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_extract_skinning",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_extract_skinning","name":"_extract_skinning","callable_type":"module_functions","line":507,"end_line":549,"signature":{"args":["node","vertex_count","skeleton_id","bone_indices","bone_weights"],"positional_count":2,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_palette_model_for_node_line_552_e008b162_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "bas_attachment_palette_model_for_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"bas_attachment_palette_model_for_node","name":"bas_attachment_palette_model_for_node","callable_type":"module_functions","line":552,"end_line":576,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mesh_model_matrix_for_node_line_579_7a36d755_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "mesh_model_matrix_for_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"mesh_model_matrix_for_node","name":"mesh_model_matrix_for_node","callable_type":"module_functions","line":579,"end_line":587,"signature":{"args":["node","anim_pose"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_subtree_nodes_line_590_c7e0370e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_subtree_nodes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_subtree_nodes","name":"_bas_attachment_subtree_nodes","callable_type":"module_functions","line":590,"end_line":601,"signature":{"args":["root"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& texture_image_to_rgba8_line_604_dba24dc9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "texture_image_to_rgba8",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"texture_image_to_rgba8","name":"texture_image_to_rgba8","callable_type":"module_functions","line":604,"end_line":624,"signature":{"args":["texture_data"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_uv_array_line_627_f48a4217_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_node_uv_array",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_node_uv_array","name":"_node_uv_array","callable_type":"module_functions","line":627,"end_line":649,"signature":{"args":["node","attr","count"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& material_data_line_652_f91a8721_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_material_data",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_material_data","name":"_material_data","callable_type":"module_functions","line":652,"end_line":715,"signature":{"args":["node","textures"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& texture_data_line_718_f11f351f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_texture_data",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_texture_data","name":"_texture_data","callable_type":"module_functions","line":718,"end_line":736,"signature":{"args":["name","textures"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_has_lightmap_line_739_ec27445f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_node_has_lightmap",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_node_has_lightmap","name":"_node_has_lightmap","callable_type":"module_functions","line":739,"end_line":748,"signature":{"args":["node","lightmap_name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& alpha_mode_line_751_5b17aae8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_alpha_mode",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_alpha_mode","name":"_alpha_mode","callable_type":"module_functions","line":751,"end_line":767,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& blend_mode_line_770_7ad06fd8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_blend_mode",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_blend_mode","name":"_blend_mode","callable_type":"module_functions","line":770,"end_line":785,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sprite_alpha_source_line_788_1fbd6397_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_sprite_alpha_source",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_sprite_alpha_source","name":"_sprite_alpha_source","callable_type":"module_functions","line":788,"end_line":797,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sprite_glow_line_800_fffe5bfb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_sprite_glow",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_sprite_glow","name":"_sprite_glow","callable_type":"module_functions","line":800,"end_line":810,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& is_saber_hilt_line_813_8bbed6e1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_is_saber_hilt",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_is_saber_hilt","name":"_is_saber_hilt","callable_type":"module_functions","line":813,"end_line":820,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& has_sprite_material_override_line_823_ce0579b4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_has_sprite_material_override",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_has_sprite_material_override","name":"_has_sprite_material_override","callable_type":"module_functions","line":823,"end_line":829,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_world_transform_line_832_8a0acaf4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_node_world_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_node_world_transform","name":"_node_world_transform","callable_type":"module_functions","line":832,"end_line":852,"signature":{"args":["node","anim_pose"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_world_matrix_line_855_b56aeb9c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "node_world_matrix",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"node_world_matrix","name":"node_world_matrix","callable_type":"module_functions","line":855,"end_line":878,"signature":{"args":["node","anim_pose"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_root_for_node_line_881_fc1375c3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_root_for_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_root_for_node","name":"_bas_attachment_root_for_node","callable_type":"module_functions","line":881,"end_line":889,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_effective_pose_for_node_line_892_2964cc0a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_effective_pose_for_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_effective_pose_for_node","name":"_bas_attachment_effective_pose_for_node","callable_type":"module_functions","line":892,"end_line":949,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_socket_node_line_952_c843adcc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_socket_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_socket_node","name":"_bas_attachment_socket_node","callable_type":"module_functions","line":952,"end_line":972,"signature":{"args":["bas_root"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_world_transform_line_975_5e5d0edc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_world_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_world_transform","name":"_bas_attachment_world_transform","callable_type":"module_functions","line":975,"end_line":1034,"signature":{"args":["node","bas_root","anim_pose"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_pose_mode_for_root_line_1037_ad40b926_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_pose_mode_for_root",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_pose_mode_for_root","name":"_bas_attachment_pose_mode_for_root","callable_type":"module_functions","line":1037,"end_line":1053,"signature":{"args":["bas_root","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_pose_applies_to_root_line_1056_fda3d3ac_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_pose_applies_to_root",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_pose_applies_to_root","name":"_bas_attachment_pose_applies_to_root","callable_type":"module_functions","line":1056,"end_line":1057,"signature":{"args":["bas_root","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_head_attachment_has_inherited_pose_tracks_line_1060_58a53a90_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_head_attachment_has_inherited_pose_tracks",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_head_attachment_has_inherited_pose_tracks","name":"_bas_head_attachment_has_inherited_pose_tracks","callable_type":"module_functions","line":1060,"end_line":1083,"signature":{"args":["bas_root","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_inherited_head_pose_node_allowed_line_1086_36e30abb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_inherited_head_pose_node_allowed",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_inherited_head_pose_node_allowed","name":"_bas_inherited_head_pose_node_allowed","callable_type":"module_functions","line":1086,"end_line":1088,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_head_attachment_local_pose_node_allowed_name_line_1091_0259f1df_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_head_attachment_local_pose_node_allowed_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_head_attachment_local_pose_node_allowed_name","name":"_bas_head_attachment_local_pose_node_allowed_name","callable_type":"module_functions","line":1091,"end_line":1103,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pose_node_for_transform_line_1106_d54c4f76_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_pose_node_for_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_pose_node_for_transform","name":"_pose_node_for_transform","callable_type":"module_functions","line":1106,"end_line":1121,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_local_transform_line_1124_852c5d58_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_bas_attachment_local_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_bas_attachment_local_transform","name":"_bas_attachment_local_transform","callable_type":"module_functions","line":1124,"end_line":1163,"signature":{"args":["node","bas_root"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& animated_node_world_transform_line_1166_122268f5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_animated_node_world_transform",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_animated_node_world_transform","name":"_animated_node_world_transform","callable_type":"module_functions","line":1166,"end_line":1249,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& material_color_line_1252_3c10f578_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_material_color",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_material_color","name":"_material_color","callable_type":"module_functions","line":1252,"end_line":1260,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_revision_line_1263_37f8d7bd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_node_revision",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_node_revision","name":"_node_revision","callable_type":"module_functions","line":1263,"end_line":1268,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& clamp01_line_1271_5850941f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_clamp01",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_clamp01","name":"_clamp01","callable_type":"module_functions","line":1271,"end_line":1272,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& clean_tex_name_line_1275_04a02cb4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::mesh_render_data",
        "src/core/rendering/mesh_render_data.py",
        "_clean_tex_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::mesh_render_data","python_file":"src/core/rendering/mesh_render_data.py","qualname":"_clean_tex_name","name":"_clean_tex_name","callable_type":"module_functions","line":1275,"end_line":1283,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ray_triangle_intersection_line_63_7b537833_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::picking",
        "src/core/rendering/picking.py",
        "ray_triangle_intersection",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::picking","python_file":"src/core/rendering/picking.py","qualname":"ray_triangle_intersection","name":"ray_triangle_intersection","callable_type":"module_functions","line":63,"end_line":87,"signature":{"args":["origin","direction","v0","v1","v2"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ray_intersects_aabb_line_90_8f71a125_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::picking",
        "src/core/rendering/picking.py",
        "ray_intersects_aabb",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::picking","python_file":"src/core/rendering/picking.py","qualname":"ray_intersects_aabb","name":"ray_intersects_aabb","callable_type":"module_functions","line":90,"end_line":111,"signature":{"args":["origin","direction","bb_min","bb_max"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& triangle_normal_line_114_06e9e20d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::picking",
        "src/core/rendering/picking.py",
        "triangle_normal",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::picking","python_file":"src/core/rendering/picking.py","qualname":"triangle_normal","name":"triangle_normal","callable_type":"module_functions","line":114,"end_line":124,"signature":{"args":["v0","v1","v2"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& vec3_line_277_cc1965b1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::picking",
        "src/core/rendering/picking.py",
        "_vec3",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::picking","python_file":"src/core/rendering/picking.py","qualname":"_vec3","name":"_vec3","callable_type":"module_functions","line":277,"end_line":279,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bounds_line_282_1bddcb2f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::picking",
        "src/core/rendering/picking.py",
        "_bounds",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::picking","python_file":"src/core/rendering/picking.py","qualname":"_bounds","name":"_bounds","callable_type":"module_functions","line":282,"end_line":290,"signature":{"args":["points"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_renderer_backend_line_66_6420bbbf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_backend",
        "src/core/rendering/renderer_backend.py",
        "normalize_renderer_backend",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_backend","python_file":"src/core/rendering/renderer_backend.py","qualname":"normalize_renderer_backend","name":"normalize_renderer_backend","callable_type":"module_functions","line":66,"end_line":70,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& supported_renderer_backend_line_73_e099ca56_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_backend",
        "src/core/rendering/renderer_backend.py",
        "supported_renderer_backend",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_backend","python_file":"src/core/rendering/renderer_backend.py","qualname":"supported_renderer_backend","name":"supported_renderer_backend","callable_type":"module_functions","line":73,"end_line":77,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderer_backend_label_line_80_7ea56790_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_backend",
        "src/core/rendering/renderer_backend.py",
        "renderer_backend_label",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_backend","python_file":"src/core/rendering/renderer_backend.py","qualname":"renderer_backend_label","name":"renderer_backend_label","callable_type":"module_functions","line":80,"end_line":87,"signature":{"args":["backend"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& material_texture_key_line_262_2ea67722_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "material_texture_key",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"material_texture_key","name":"material_texture_key","callable_type":"module_functions","line":262,"end_line":265,"signature":{"args":["material_data"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& batch_key_for_mesh_line_268_a84a6624_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "batch_key_for_mesh",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"batch_key_for_mesh","name":"batch_key_for_mesh","callable_type":"module_functions","line":268,"end_line":279,"signature":{"args":["mesh_data","material_data","pipeline_key","category","culling_mode"],"positional_count":2,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& group_render_batches_line_282_f7d9f499_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "group_render_batches",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"group_render_batches","name":"group_render_batches","callable_type":"module_functions","line":282,"end_line":304,"signature":{"args":["items","pipeline_key","category"],"positional_count":1,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& instancing_summary_line_307_7d0d8a8b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "instancing_summary",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"instancing_summary","name":"instancing_summary","callable_type":"module_functions","line":307,"end_line":332,"signature":{"args":["items"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& extract_frustum_planes_line_335_0f2aa8ca_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "extract_frustum_planes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"extract_frustum_planes","name":"extract_frustum_planes","callable_type":"module_functions","line":335,"end_line":345,"signature":{"args":["mvp"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bounds_intersects_frustum_line_348_34e4da1a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "bounds_intersects_frustum",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"bounds_intersects_frustum","name":"bounds_intersects_frustum","callable_type":"module_functions","line":348,"end_line":359,"signature":{"args":["bounds","planes"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& texture_array_groups_line_362_8742af4e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "texture_array_groups",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"texture_array_groups","name":"texture_array_groups","callable_type":"module_functions","line":362,"end_line":368,"signature":{"args":["textures"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& array_len_line_371_af729207_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "_array_len",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"_array_len","name":"_array_len","callable_type":"module_functions","line":371,"end_line":389,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& row_add_line_392_e505cc38_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "_row_add",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"_row_add","name":"_row_add","callable_type":"module_functions","line":392,"end_line":393,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& row_sub_line_396_98ba1108_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "_row_sub",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"_row_sub","name":"_row_sub","callable_type":"module_functions","line":396,"end_line":397,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_plane_line_400_c1e5cf03_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_performance",
        "src/core/rendering/renderer_performance.py",
        "_normalize_plane",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_performance","python_file":"src/core/rendering/renderer_performance.py","qualname":"_normalize_plane","name":"_normalize_plane","callable_type":"module_functions","line":400,"end_line":405,"signature":{"args":["plane"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_bool_line_10_5d610f71_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_settings",
        "src/core/rendering/renderer_settings.py",
        "_safe_bool",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_settings","python_file":"src/core/rendering/renderer_settings.py","qualname":"_safe_bool","name":"_safe_bool","callable_type":"module_functions","line":10,"end_line":21,"signature":{"args":["value","default"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_int_line_24_8e8fd9ce_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_settings",
        "src/core/rendering/renderer_settings.py",
        "_safe_int",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_settings","python_file":"src/core/rendering/renderer_settings.py","qualname":"_safe_int","name":"_safe_int","callable_type":"module_functions","line":24,"end_line":28,"signature":{"args":["value","default","minimum"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_float_line_31_75f11871_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::renderer_settings",
        "src/core/rendering/renderer_settings.py",
        "_safe_float",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::renderer_settings","python_file":"src/core/rendering/renderer_settings.py","qualname":"_safe_float","name":"_safe_float","callable_type":"module_functions","line":31,"end_line":35,"signature":{"args":["value","default","minimum"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_skeleton_render_data_line_80_8beff479_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "build_skeleton_render_data",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"build_skeleton_render_data","name":"build_skeleton_render_data","callable_type":"module_functions","line":80,"end_line":174,"signature":{"args":["model","anim_pose","selected_node","selected_nodes","hovered_node","show_dots","show_links","show_names","show_axes"],"positional_count":1,"keyword_only_count":8,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cached_world_position_resolver_line_177_96f3e227_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_cached_world_position_resolver",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_world_position_resolver","name":"_cached_world_position_resolver","callable_type":"module_functions","line":177,"end_line":220,"signature":{"args":["anim_pose"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& extract_skinning_arrays_line_223_4676a091_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "extract_skinning_arrays",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"extract_skinning_arrays","name":"extract_skinning_arrays","callable_type":"module_functions","line":223,"end_line":296,"signature":{"args":["node","vertex_count","skeleton_id","bone_indices","bone_weights"],"positional_count":2,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cpu_skin_vbo_arrays_line_299_8baa9173_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "cpu_skin_vbo_arrays",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"cpu_skin_vbo_arrays","name":"cpu_skin_vbo_arrays","callable_type":"module_functions","line":299,"end_line":372,"signature":{"args":["node","positions","normals","skinning","anim_pose","model"],"positional_count":6,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_root_local_skin_palette_line_375_3fcd25db_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "bas_attachment_root_local_skin_palette",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"bas_attachment_root_local_skin_palette","name":"bas_attachment_root_local_skin_palette","callable_type":"module_functions","line":375,"end_line":397,"signature":{"args":["node","palette","anim_pose"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bas_attachment_source_local_root_matrix_line_400_6cd81f41_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_bas_attachment_source_local_root_matrix",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_bas_attachment_source_local_root_matrix","name":"_bas_attachment_source_local_root_matrix","callable_type":"module_functions","line":400,"end_line":431,"signature":{"args":["root","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_palette_flat_bytes_line_434_c134d52b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "skin_palette_flat_bytes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"skin_palette_flat_bytes","name":"skin_palette_flat_bytes","callable_type":"module_functions","line":434,"end_line":452,"signature":{"args":["palette","max_bones"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cached_matrix_palette_uploader_line_455_58be21bd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_cached_matrix_palette_uploader",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_matrix_palette_uploader","name":"_cached_matrix_palette_uploader","callable_type":"module_functions","line":455,"end_line":473,"signature":{"args":["model","max_bones","uploader_cls"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skinning_palette_model_for_node_line_476_193696ae_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_skinning_palette_model_for_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_skinning_palette_model_for_node","name":"_skinning_palette_model_for_node","callable_type":"module_functions","line":476,"end_line":486,"signature":{"args":["node","model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix_palette_uploader_cache_key_line_489_d2f67a8f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_matrix_palette_uploader_cache_key",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_matrix_palette_uploader_cache_key","name":"_matrix_palette_uploader_cache_key","callable_type":"module_functions","line":489,"end_line":519,"signature":{"args":["model","max_bones"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cpu_skin_positions_line_522_a4e14052_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "cpu_skin_positions",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"cpu_skin_positions","name":"cpu_skin_positions","callable_type":"module_functions","line":522,"end_line":565,"signature":{"args":["node","positions","skinning","anim_pose","model","anim_base_pose"],"positional_count":6,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_weight_rows_line_568_82ae484d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_normalize_weight_rows",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_normalize_weight_rows","name":"_normalize_weight_rows","callable_type":"module_functions","line":568,"end_line":577,"signature":{"args":["weights"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& model_nodes_line_580_f434f2db_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_model_nodes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_model_nodes","name":"_model_nodes","callable_type":"module_functions","line":580,"end_line":584,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& is_bone_node_line_587_82644d7b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_is_bone_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_is_bone_node","name":"_is_bone_node","callable_type":"module_functions","line":587,"end_line":599,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& nearest_bone_ancestor_line_602_56a86531_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_nearest_bone_ancestor",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_nearest_bone_ancestor","name":"_nearest_bone_ancestor","callable_type":"module_functions","line":602,"end_line":613,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_world_position_line_616_f9fdec7f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_node_world_position",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_node_world_position","name":"_node_world_position","callable_type":"module_functions","line":616,"end_line":631,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& animated_world_position_line_634_d88f7518_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_animated_world_position",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_animated_world_position","name":"_animated_world_position","callable_type":"module_functions","line":634,"end_line":668,"signature":{"args":["node","anim_pose"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& distance_line_671_272ee1dd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_distance",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_distance","name":"_distance","callable_type":"module_functions","line":671,"end_line":674,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bone_colour_hint_line_677_18d8061f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_bone_colour_hint",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_bone_colour_hint","name":"_bone_colour_hint","callable_type":"module_functions","line":677,"end_line":684,"signature":{"args":["node","selected","hovered"],"positional_count":1,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_revision_line_687_806e2dee_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_skin_revision",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_skin_revision","name":"_skin_revision","callable_type":"module_functions","line":687,"end_line":696,"signature":{"args":["node","vertex_count"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& root_model_from_node_line_699_94251bf8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_root_model_from_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_root_model_from_node","name":"_root_model_from_node","callable_type":"module_functions","line":699,"end_line":700,"signature":{"args":["_node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_display_mode_line_82_fd5baebd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::viewport_display",
        "src/core/rendering/viewport_display.py",
        "normalize_display_mode",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::viewport_display","python_file":"src/core/rendering/viewport_display.py","qualname":"normalize_display_mode","name":"normalize_display_mode","callable_type":"module_functions","line":82,"end_line":110,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& display_mode_values_line_113_303ced51_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::viewport_display",
        "src/core/rendering/viewport_display.py",
        "display_mode_values",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::viewport_display","python_file":"src/core/rendering/viewport_display.py","qualname":"display_mode_values","name":"display_mode_values","callable_type":"module_functions","line":113,"end_line":114,"signature":{"args":["modes"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_viewport_navigation_profile_line_78_0c3f593a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::viewport_navigation",
        "src/core/rendering/viewport_navigation.py",
        "normalize_viewport_navigation_profile",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::viewport_navigation","python_file":"src/core/rendering/viewport_navigation.py","qualname":"normalize_viewport_navigation_profile","name":"normalize_viewport_navigation_profile","callable_type":"module_functions","line":78,"end_line":88,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& viewport_profile_label_line_91_a83aba40_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::viewport_navigation",
        "src/core/rendering/viewport_navigation.py",
        "viewport_profile_label",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::viewport_navigation","python_file":"src/core/rendering/viewport_navigation.py","qualname":"viewport_profile_label","name":"viewport_profile_label","callable_type":"module_functions","line":91,"end_line":93,"signature":{"args":["key"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& has_modifier_line_96_8bac0a69_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::viewport_navigation",
        "src/core/rendering/viewport_navigation.py",
        "has_modifier",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::viewport_navigation","python_file":"src/core/rendering/viewport_navigation.py","qualname":"has_modifier","name":"has_modifier","callable_type":"module_functions","line":96,"end_line":97,"signature":{"args":["modifiers","modifier"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& load_mesh_shader_line_6_2d673ba0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shaders",
        "src/core/rendering/wgpu_shaders.py",
        "_load_mesh_shader",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shaders","python_file":"src/core/rendering/wgpu_shaders.py","qualname":"_load_mesh_shader","name":"_load_mesh_shader","callable_type":"module_functions","line":6,"end_line":11,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& load_skinned_mesh_shader_line_14_843f9a71_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shaders",
        "src/core/rendering/wgpu_shaders.py",
        "_load_skinned_mesh_shader",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shaders","python_file":"src/core/rendering/wgpu_shaders.py","qualname":"_load_skinned_mesh_shader","name":"_load_skinned_mesh_shader","callable_type":"module_functions","line":14,"end_line":16,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rgb_float_line_127_9d78f9a4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_rgb_float",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_rgb_float","name":"_rgb_float","callable_type":"module_functions","line":127,"end_line":128,"signature":{"args":["color"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& blend_rgb_line_131_eeb9479a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_blend_rgb",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_blend_rgb","name":"_blend_rgb","callable_type":"module_functions","line":131,"end_line":133,"signature":{"args":["a","b","t"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& relative_luma_line_136_ac138b90_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_relative_luma",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_relative_luma","name":"_relative_luma","callable_type":"module_functions","line":136,"end_line":138,"signature":{"args":["color"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rgba8_line_141_bd9365fb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_rgba8",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_rgba8","name":"_rgba8","callable_type":"module_functions","line":141,"end_line":142,"signature":{"args":["color","alpha"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& point_distance_line_145_c54244b6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_point_distance",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_point_distance","name":"_point_distance","callable_type":"module_functions","line":145,"end_line":146,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& joint_marker_segments_line_149_bb4dab87_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_joint_marker_segments",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_joint_marker_segments","name":"_joint_marker_segments","callable_type":"module_functions","line":149,"end_line":159,"signature":{"args":["point","selected"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& srgb_channel_to_linear_line_162_43d6320e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_srgb_channel_to_linear",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_srgb_channel_to_linear","name":"_srgb_channel_to_linear","callable_type":"module_functions","line":162,"end_line":166,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& srgb_to_linear_line_169_cbc572d3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_srgb_to_linear",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_srgb_to_linear","name":"_srgb_to_linear","callable_type":"module_functions","line":169,"end_line":173,"signature":{"args":["color"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& format_is_srgb_line_176_977aa9e8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_format_is_srgb",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_format_is_srgb","name":"_format_is_srgb","callable_type":"module_functions","line":176,"end_line":177,"signature":{"args":["format_name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mat4_perspective_wgpu_line_180_30daf050_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_mat4_perspective_wgpu",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_mat4_perspective_wgpu","name":"_mat4_perspective_wgpu","callable_type":"module_functions","line":180,"end_line":190,"signature":{"args":["fov_y","aspect","near","far"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mat4_lookat_line_193_5cb75700_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_mat4_lookat",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_mat4_lookat","name":"_mat4_lookat","callable_type":"module_functions","line":193,"end_line":219,"signature":{"args":["eye","center","up"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mat4_tobytes_line_222_f9135a93_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_mat4_tobytes",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_mat4_tobytes","name":"_mat4_tobytes","callable_type":"module_functions","line":222,"end_line":225,"signature":{"args":["m"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& adapter_info_dict_line_228_dcc235f2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::core::rendering::wgpu_shared",
        "src/core/rendering/wgpu_shared.py",
        "_adapter_info_dict",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::core::rendering::wgpu_shared","python_file":"src/core/rendering/wgpu_shared.py","qualname":"_adapter_info_dict","name":"_adapter_info_dict","callable_type":"module_functions","line":228,"end_line":233,"signature":{"args":["adapter"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        project_vertices_np_line_86_3ca949f7_native(),
        frustum_cull_np_line_113_9bccb4dd_native(),
        depth_sort_np_line_136_478fd4c3_native(),
        fconstructe_uv_filter_np_line_151_d7d62dcc_native(),
        shade_colors_np_line_165_dd196f7d_native(),
        rasterize_triangle_numpy_line_195_4e1c8ac8_native(),
        rasterize_triangle_jit_line_308_297096d2_native(),
        rasterize_frame_jit_line_383_c5df2ead_native(),
        flat_shade_frame_jit_line_478_01aa72ee_native(),
        warmup_jit_line_526_9ee39da9_native(),
        rasterize_triangle_line_576_3f417fc3_native(),
        rasterize_frame_line_614_790112b7_native(),
        flat_shade_frame_line_670_dad8f1ae_native(),
        hex_to_rgb_float_line_6_d961967c_native(),
        hex_to_rgb_tuple_line_24_2755e159_native(),
        rgb_str_to_tuple_line_34_cee92d1e_native(),
        paste_textured_triangle_line_39_407f8a8a_native(),
        paste_lightmap_triangle_line_681_2912f524_native(),
        warmup_jit_line_93_0e6ef2ee_native(),
        accel_proj_verts_line_94_0b3e259f_native(),
        accel_frustum_cull_line_95_0a1d8011_native(),
        accel_depth_sort_line_96_b7ddf1bc_native(),
        accel_rasterize_frame_line_97_c1f0ed8b_native(),
        accel_flat_shade_frame_line_98_de274f7a_native(),
        accel_shade_colors_line_99_01acb5e5_native(),
        gr_probe_line_10_574234dd_native(),
        rasterize_triangle_textured_line_13_0e54f6b1_native(),
        debug_draw_table_line_42_9ec84b51_native(),
        debug_uv_channel_table_line_95_a1f860e8_native(),
        debug_texture_cache_table_line_179_01c72050_native(),
        debug_material_role_table_line_275_fb8306c6_native(),
        path_from_env_line_19_14f3c397_native(),
        int_env_clamped_line_23_d561e4b4_native(),
        gl_state_trace_path_line_31_dc7a1b70_native(),
        lm_data_dump_path_line_35_42ca528c_native(),
        skin_dump_path_line_39_fe55d8b8_native(),
        debug_visualize_mode_line_43_5b215ffd_native(),
        lm_composite_mode_line_47_d363b831_native(),
        jsonable_gl_value_line_34_1ede079b_native(),
        safe_gl_attr_line_46_f3c09db3_native(),
        uniform_trace_value_line_53_a664db23_native(),
        build_gl_state_trace_record_line_63_661c5f41_native(),
        append_gl_state_trace_line_124_86a67054_native(),
        first_uv_pairs_line_135_da46e2f2_native(),
        first_vbo_uv_pairs_line_145_8a1604a1_native(),
        texture_content_stats_line_155_f01bae93_native(),
        lightmap_role_info_line_209_0ccec99b_native(),
        build_lm_data_dump_record_line_248_50e702ce_native(),
        append_jsonl_record_line_295_860d61fe_native(),
        matrix4_json_line_306_ba4cf4dd_native(),
        matrix4_inverse_json_line_315_0b488bbd_native(),
        matrix4_mul_json_line_324_613234fd_native(),
        matrix4_det_value_line_333_10bbe3a5_native(),
        uploaded_palette_array_from_uploader_line_342_fddf1b89_native(),
        homogeneous_position_json_line_358_ac991133_native(),
        first_divergence_stage_line_369_c7da1b20_native(),
        matrix_max_abs_delta_line_383_59f01372_native(),
        matrix_translation_norm_line_394_e64780c0_native(),
        matrix_rotation_only_line_407_b4c89a01_native(),
        qbone_inverse_bind_json_line_423_dc625269_native(),
        qbone_direct_bind_json_line_452_87c34f93_native(),
        qbone_matrix_np_line_465_e2e68a5e_native(),
        node_world_matrix_for_pose_np_line_485_d8054911_native(),
        node_pose_chain_records_line_513_2a4aab68_native(),
        quat_xyzw_to_mat4_np_line_534_d9a3b5ee_native(),
        xoreos_first_frame_orientation_matrix_line_557_fce39b4e_native(),
        skin_3g_matrix_for_formula_line_618_9cc7f336_native(),
        skin_3g_role_for_bone_line_666_95ed8883_native(),
        skin_3g_role_priority_line_679_301987b6_native(),
        select_skin_3g_probe_vertices_line_704_12e70976_native(),
        skin_bind_equivalence_record_line_732_e3864866_native(),
        skin_3g_candidate_records_line_765_95075d52_native(),
        skin_live_slot_records_line_1233_88a63431_native(),
        build_skin_dump_record_line_1336_1e8ff3a1_native(),
        pose_node_transform_line_1669_c2989b35_native(),
        select_skin_probe_vertex_line_1687_bc6f7e2f_native(),
        node_parent_chain_names_line_1703_3065b3a0_native(),
        node_uses_single_tile_atlas_line_1712_7c035216_native(),
        should_auto_clamp_diffuse_line_1731_1c306c28_native(),
        compute_model_bounds_line_16_cf1ab2a2_native(),
        apply_txi_from_textures_to_model_line_118_3dff2d89_native(),
        split_vbo_attributes_for_gpu_line_21_9cff8882_native(),
        collect_hardware_diagnostics_line_94_5881f1f3_native(),
        cpu_name_line_127_c7716d7e_native(),
        cpu_flags_line_154_660bb9e1_native(),
        physical_core_count_line_162_6f5fbb6e_native(),
        logical_thread_count_line_175_01d8bc20_native(),
        adapter_name_line_181_d50546a1_native(),
        cpuinfo_payload_line_203_2b37f212_native(),
        windows_processor_info_line_214_64580fab_native(),
        architecture_label_line_255_c7c480b1_native(),
        windows_processor_feature_flags_line_275_9ae4f93b_native(),
        windows_gpu_adapter_name_line_299_16f551e4_native(),
        safe_int_line_351_3f7f77a2_native(),
        iter_mesh_render_data_line_65_fa47e988_native(),
        model_nodes_line_211_661ae3a2_native(),
        node_is_renderable_mesh_line_225_e3ba8c3b_native(),
        extract_node_arrays_line_239_41751f47_native(),
        skinned_lbs_vbo_cache_key_line_326_3546a59b_native(),
        static_vbo_cache_key_line_346_d5eafd23_native(),
        get_skinned_lbs_vbo_cache_line_362_d6f98c35_native(),
        set_skinned_lbs_vbo_cache_line_374_25580cd0_native(),
        smooth_render_normals_line_383_3400ba22_native(),
        coerce_normal_array_line_440_fec0c1af_native(),
        area_weighted_normal_accum_line_460_c1f111bb_native(),
        normalize_rows_line_487_a0d58bc1_native(),
        extract_skinning_line_507_5c8210f3_native(),
        bas_attachment_palette_model_for_node_line_552_e008b162_native(),
        mesh_model_matrix_for_node_line_579_7a36d755_native(),
        bas_attachment_subtree_nodes_line_590_c7e0370e_native(),
        texture_image_to_rgba8_line_604_dba24dc9_native(),
        node_uv_array_line_627_f48a4217_native(),
        material_data_line_652_f91a8721_native(),
        texture_data_line_718_f11f351f_native(),
        node_has_lightmap_line_739_ec27445f_native(),
        alpha_mode_line_751_5b17aae8_native(),
        blend_mode_line_770_7ad06fd8_native(),
        sprite_alpha_source_line_788_1fbd6397_native(),
        sprite_glow_line_800_fffe5bfb_native(),
        is_saber_hilt_line_813_8bbed6e1_native(),
        has_sprite_material_override_line_823_ce0579b4_native(),
        node_world_transform_line_832_8a0acaf4_native(),
        node_world_matrix_line_855_b56aeb9c_native(),
        bas_attachment_root_for_node_line_881_fc1375c3_native(),
        bas_attachment_effective_pose_for_node_line_892_2964cc0a_native(),
        bas_attachment_socket_node_line_952_c843adcc_native(),
        bas_attachment_world_transform_line_975_5e5d0edc_native(),
        bas_attachment_pose_mode_for_root_line_1037_ad40b926_native(),
        bas_attachment_pose_applies_to_root_line_1056_fda3d3ac_native(),
        bas_head_attachment_has_inherited_pose_tracks_line_1060_58a53a90_native(),
        bas_inherited_head_pose_node_allowed_line_1086_36e30abb_native(),
        bas_head_attachment_local_pose_node_allowed_name_line_1091_0259f1df_native(),
        pose_node_for_transform_line_1106_d54c4f76_native(),
        bas_attachment_local_transform_line_1124_852c5d58_native(),
        animated_node_world_transform_line_1166_122268f5_native(),
        material_color_line_1252_3c10f578_native(),
        node_revision_line_1263_37f8d7bd_native(),
        clamp01_line_1271_5850941f_native(),
        clean_tex_name_line_1275_04a02cb4_native(),
        ray_triangle_intersection_line_63_7b537833_native(),
        ray_intersects_aabb_line_90_8f71a125_native(),
        triangle_normal_line_114_06e9e20d_native(),
        vec3_line_277_cc1965b1_native(),
        bounds_line_282_1bddcb2f_native(),
        normalize_renderer_backend_line_66_6420bbbf_native(),
        supported_renderer_backend_line_73_e099ca56_native(),
        renderer_backend_label_line_80_7ea56790_native(),
        material_texture_key_line_262_2ea67722_native(),
        batch_key_for_mesh_line_268_a84a6624_native(),
        group_render_batches_line_282_f7d9f499_native(),
        instancing_summary_line_307_7d0d8a8b_native(),
        extract_frustum_planes_line_335_0f2aa8ca_native(),
        bounds_intersects_frustum_line_348_34e4da1a_native(),
        texture_array_groups_line_362_8742af4e_native(),
        array_len_line_371_af729207_native(),
        row_add_line_392_e505cc38_native(),
        row_sub_line_396_98ba1108_native(),
        normalize_plane_line_400_c1e5cf03_native(),
        safe_bool_line_10_5d610f71_native(),
        safe_int_line_24_8e8fd9ce_native(),
        safe_float_line_31_75f11871_native(),
        build_skeleton_render_data_line_80_8beff479_native(),
        cached_world_position_resolver_line_177_96f3e227_native(),
        extract_skinning_arrays_line_223_4676a091_native(),
        cpu_skin_vbo_arrays_line_299_8baa9173_native(),
        bas_attachment_root_local_skin_palette_line_375_3fcd25db_native(),
        bas_attachment_source_local_root_matrix_line_400_6cd81f41_native(),
        skin_palette_flat_bytes_line_434_c134d52b_native(),
        cached_matrix_palette_uploader_line_455_58be21bd_native(),
        skinning_palette_model_for_node_line_476_193696ae_native(),
        matrix_palette_uploader_cache_key_line_489_d2f67a8f_native(),
        cpu_skin_positions_line_522_a4e14052_native(),
        normalize_weight_rows_line_568_82ae484d_native(),
        model_nodes_line_580_f434f2db_native(),
        is_bone_node_line_587_82644d7b_native(),
        nearest_bone_ancestor_line_602_56a86531_native(),
        node_world_position_line_616_f9fdec7f_native(),
        animated_world_position_line_634_d88f7518_native(),
        distance_line_671_272ee1dd_native(),
        bone_colour_hint_line_677_18d8061f_native(),
        skin_revision_line_687_806e2dee_native(),
        root_model_from_node_line_699_94251bf8_native(),
        normalize_display_mode_line_82_fd5baebd_native(),
        display_mode_values_line_113_303ced51_native(),
        normalize_viewport_navigation_profile_line_78_0c3f593a_native(),
        viewport_profile_label_line_91_a83aba40_native(),
        has_modifier_line_96_8bac0a69_native(),
        load_mesh_shader_line_6_2d673ba0_native(),
        load_skinned_mesh_shader_line_14_843f9a71_native(),
        rgb_float_line_127_9d78f9a4_native(),
        blend_rgb_line_131_eeb9479a_native(),
        relative_luma_line_136_ac138b90_native(),
        rgba8_line_141_bd9365fb_native(),
        point_distance_line_145_c54244b6_native(),
        joint_marker_segments_line_149_bb4dab87_native(),
        srgb_channel_to_linear_line_162_43d6320e_native(),
        srgb_to_linear_line_169_cbc572d3_native(),
        format_is_srgb_line_176_977aa9e8_native(),
        mat4_perspective_wgpu_line_180_30daf050_native(),
        mat4_lookat_line_193_5cb75700_native(),
        mat4_tobytes_line_222_f9135a93_native(),
        adapter_info_dict_line_228_dcc235f2_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::rendering
