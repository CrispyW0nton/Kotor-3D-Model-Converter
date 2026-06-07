#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_adapters_gpu {

const char* src_adapters_gpu_lightmap_gpu_solver_kind_code_line_278_064e698f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.GPU","python_module":"src.adapters.gpu.lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"_kind_code","name":"_kind_code","kind":"module_functions","line":278,"end_line":288,"signature":{"args":["light"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_gpu_lightmap_gpu_solver_vec3_line_291_f6acbc46_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.GPU","python_module":"src.adapters.gpu.lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"_vec3","name":"_vec3","kind":"module_functions","line":291,"end_line":295,"signature":{"args":["value","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_gpu_moderngl_context_gl_context_backend_candidates_line_19_4983a56d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.GPU","python_module":"src.adapters.gpu.moderngl_context","python_file":"src/adapters/gpu/moderngl_context.py","qualname":"_gl_context_backend_candidates","name":"_gl_context_backend_candidates","kind":"module_functions","line":19,"end_line":32,"signature":{"args":["os_name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_gpu_moderngl_context_create_moderngl_standalone_context_line_35_8986cc55_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.GPU","python_module":"src.adapters.gpu.moderngl_context","python_file":"src/adapters/gpu/moderngl_context.py","qualname":"_create_moderngl_standalone_context","name":"_create_moderngl_standalone_context","kind":"module_functions","line":35,"end_line":48,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_gpu_viewport_probe_gr_gpu_probe_line_16_3850cbae_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.GPU","python_module":"src.adapters.gpu.viewport_probe","python_file":"src/adapters/gpu/viewport_probe.py","qualname":"_gr_gpu_probe","name":"_gr_gpu_probe","kind":"module_functions","line":16,"end_line":61,"signature":{"args":["node","wp","wo","is_id_rot","composite_off"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/gpu/lightmap_gpu_solver.py", "_kind_code", "module_functions", &src_adapters_gpu_lightmap_gpu_solver_kind_code_line_278_064e698f_descriptor_json},
        {"src/adapters/gpu/lightmap_gpu_solver.py", "_vec3", "module_functions", &src_adapters_gpu_lightmap_gpu_solver_vec3_line_291_f6acbc46_descriptor_json},
        {"src/adapters/gpu/moderngl_context.py", "_gl_context_backend_candidates", "module_functions", &src_adapters_gpu_moderngl_context_gl_context_backend_candidates_line_19_4983a56d_descriptor_json},
        {"src/adapters/gpu/moderngl_context.py", "_create_moderngl_standalone_context", "module_functions", &src_adapters_gpu_moderngl_context_create_moderngl_standalone_context_line_35_8986cc55_descriptor_json},
        {"src/adapters/gpu/viewport_probe.py", "_gr_gpu_probe", "module_functions", &src_adapters_gpu_viewport_probe_gr_gpu_probe_line_16_3850cbae_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_gpu
