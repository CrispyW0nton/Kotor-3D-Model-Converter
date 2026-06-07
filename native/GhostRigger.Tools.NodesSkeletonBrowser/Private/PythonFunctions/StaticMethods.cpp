#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_nodesskeletonbrowser {

const char* src_core_animation_animation_library_animationretargeter_build_map_line_372_debf3019_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.animation_library","python_file":"src/core/animation/animation_library.py","qualname":"AnimationRetargeter.build_map","name":"build_map","kind":"static_methods","line":372,"end_line":388,"signature":{"args":["mapping","case_insensitive"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_animation_animation_library_animationretargeter_from_json_line_391_cc3025a4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.animation_library","python_file":"src/core/animation/animation_library.py","qualname":"AnimationRetargeter.from_json","name":"from_json","kind":"static_methods","line":391,"end_line":395,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_animation_animation_library_animationretargeter_save_json_line_398_0daaa362_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.animation_library","python_file":"src/core/animation/animation_library.py","qualname":"AnimationRetargeter.save_json","name":"save_json","kind":"static_methods","line":398,"end_line":402,"signature":{"args":["remap","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_line_738_39b95042_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.gpu_skinning","python_file":"src/core/animation/gpu_skinning.py","qualname":"MatrixPaletteUploader.qbone_inverse_bind_matrix","name":"qbone_inverse_bind_matrix","kind":"static_methods","line":738,"end_line":754,"signature":{"args":["qbone","tbone"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_direct_bind_matrix_line_757_49040c9a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.gpu_skinning","python_file":"src/core/animation/gpu_skinning.py","qualname":"MatrixPaletteUploader.qbone_direct_bind_matrix","name":"qbone_direct_bind_matrix","kind":"static_methods","line":757,"end_line":776,"signature":{"args":["qbone","tbone"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_g5_line_779_8029ac58_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.NodesSkeletonBrowser","python_module":"src.core.animation.gpu_skinning","python_file":"src/core/animation/gpu_skinning.py","qualname":"MatrixPaletteUploader.qbone_inverse_bind_matrix_g5","name":"qbone_inverse_bind_matrix_g5","kind":"static_methods","line":779,"end_line":835,"signature":{"args":["qbone","tbone"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/animation/animation_library.py", "AnimationRetargeter.build_map", "static_methods", &src_core_animation_animation_library_animationretargeter_build_map_line_372_debf3019_descriptor_json},
        {"src/core/animation/animation_library.py", "AnimationRetargeter.from_json", "static_methods", &src_core_animation_animation_library_animationretargeter_from_json_line_391_cc3025a4_descriptor_json},
        {"src/core/animation/animation_library.py", "AnimationRetargeter.save_json", "static_methods", &src_core_animation_animation_library_animationretargeter_save_json_line_398_0daaa362_descriptor_json},
        {"src/core/animation/gpu_skinning.py", "MatrixPaletteUploader.qbone_inverse_bind_matrix", "static_methods", &src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_line_738_39b95042_descriptor_json},
        {"src/core/animation/gpu_skinning.py", "MatrixPaletteUploader.qbone_direct_bind_matrix", "static_methods", &src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_direct_bind_matrix_line_757_49040c9a_descriptor_json},
        {"src/core/animation/gpu_skinning.py", "MatrixPaletteUploader.qbone_inverse_bind_matrix_g5", "static_methods", &src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_g5_line_779_8029ac58_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_nodesskeletonbrowser
