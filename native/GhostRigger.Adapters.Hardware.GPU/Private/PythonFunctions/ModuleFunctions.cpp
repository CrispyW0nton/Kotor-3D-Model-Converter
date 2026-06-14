#include "PythonFunctions/ModuleFunctions.h"
#include "GpuAdapterContracts.h"

namespace ghostrigger::adapters::hardware::gpu {

const NativeFunctionImplementation& kind_code_line_278_064e698f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Hardware.GPU",
        "ghostrigger::adapters::hardware::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "_kind_code",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Hardware.GPU","namespace":"ghostrigger::adapters::hardware::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"_kind_code","name":"_kind_code","callable_type":"module_functions","line":278,"end_line":288,"signature":{"args":["light"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& vec3_line_291_f6acbc46_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Hardware.GPU",
        "ghostrigger::adapters::hardware::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "_vec3",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Hardware.GPU","namespace":"ghostrigger::adapters::hardware::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"_vec3","name":"_vec3","callable_type":"module_functions","line":291,"end_line":295,"signature":{"args":["value","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gl_context_backend_candidates_line_19_4983a56d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Hardware.GPU",
        "ghostrigger::adapters::hardware::gpu::moderngl_context",
        "src/adapters/gpu/moderngl_context.py",
        "_gl_context_backend_candidates",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Hardware.GPU","namespace":"ghostrigger::adapters::hardware::gpu::moderngl_context","python_file":"src/adapters/gpu/moderngl_context.py","qualname":"_gl_context_backend_candidates","name":"_gl_context_backend_candidates","callable_type":"module_functions","line":19,"end_line":32,"signature":{"args":["os_name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& create_moderngl_standalone_context_line_35_8986cc55_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Hardware.GPU",
        "ghostrigger::adapters::hardware::gpu::moderngl_context",
        "src/adapters/gpu/moderngl_context.py",
        "_create_moderngl_standalone_context",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Hardware.GPU","namespace":"ghostrigger::adapters::hardware::gpu::moderngl_context","python_file":"src/adapters/gpu/moderngl_context.py","qualname":"_create_moderngl_standalone_context","name":"_create_moderngl_standalone_context","callable_type":"module_functions","line":35,"end_line":48,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gr_gpu_probe_line_16_3850cbae_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Hardware.GPU",
        "ghostrigger::adapters::hardware::gpu::viewport_probe",
        "src/adapters/gpu/viewport_probe.py",
        "_gr_gpu_probe",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Hardware.GPU","namespace":"ghostrigger::adapters::hardware::gpu::viewport_probe","python_file":"src/adapters/gpu/viewport_probe.py","qualname":"_gr_gpu_probe","name":"_gr_gpu_probe","callable_type":"module_functions","line":16,"end_line":61,"signature":{"args":["node","wp","wo","is_id_rot","composite_off"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        kind_code_line_278_064e698f_native(),
        vec3_line_291_f6acbc46_native(),
        gl_context_backend_candidates_line_19_4983a56d_native(),
        create_moderngl_standalone_context_line_35_8986cc55_native(),
        gr_gpu_probe_line_16_3850cbae_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::hardware::gpu
