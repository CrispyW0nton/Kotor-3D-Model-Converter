#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::adapters::gpu {

const NativeFunctionImplementation& lightmapbaker_construct_line_13_ea0e7678_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_baker",
        "src/adapters/gpu/lightmap_baker.py",
        "LightmapBaker.__init__",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_baker","python_file":"src/adapters/gpu/lightmap_baker.py","qualname":"LightmapBaker.__init__","name":"__init__","callable_type":"instance_methods","line":13,"end_line":18,"signature":{"args":["self","lighting_solver"],"positional_count":1,"keyword_only_count":1,"has_vararg":true,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_construct_line_121_8c058229_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver.__init__",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver.__init__","name":"__init__","callable_type":"instance_methods","line":121,"end_line":129,"signature":{"args":["self","cpu_solver"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_solve_buffer_line_131_1afe1ce7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver.solve_buffer",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver.solve_buffer","name":"solve_buffer","callable_type":"instance_methods","line":131,"end_line":150,"signature":{"args":["self","buffer","lights","settings","shadow_solver"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_can_use_gpu_line_152_ffd61772_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver.can_use_gpu",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver.can_use_gpu","name":"can_use_gpu","callable_type":"instance_methods","line":152,"end_line":160,"signature":{"args":["self","settings","shadow_solver"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_ensure_line_162_a771dede_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver._ensure",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver._ensure","name":"_ensure","callable_type":"instance_methods","line":162,"end_line":175,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_solve_gpu_line_177_47133327_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver._solve_gpu",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver._solve_gpu","name":"_solve_gpu","callable_type":"instance_methods","line":177,"end_line":208,"signature":{"args":["self","buffer","lights","settings"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_render_direct_chunk_line_210_0fddce25_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver._render_direct_chunk",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver._render_direct_chunk","name":"_render_direct_chunk","callable_type":"instance_methods","line":210,"end_line":247,"signature":{"args":["self","pos_tex","normal_tex","lights","res","settings"],"positional_count":6,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_tex2d_line_249_324b574b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver._tex2d",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver._tex2d","name":"_tex2d","callable_type":"instance_methods","line":249,"end_line":255,"signature":{"args":["self","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapgpusolver_pack_lights_line_257_2f7fdace_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.GPU",
        "ghostrigger::adapters::gpu::lightmap_gpu_solver",
        "src/adapters/gpu/lightmap_gpu_solver.py",
        "LightmapGpuSolver._pack_lights",
        "instance_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.GPU","namespace":"ghostrigger::adapters::gpu::lightmap_gpu_solver","python_file":"src/adapters/gpu/lightmap_gpu_solver.py","qualname":"LightmapGpuSolver._pack_lights","name":"_pack_lights","callable_type":"instance_methods","line":257,"end_line":275,"signature":{"args":["self","lights"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        lightmapbaker_construct_line_13_ea0e7678_native(),
        lightmapgpusolver_construct_line_121_8c058229_native(),
        lightmapgpusolver_solve_buffer_line_131_1afe1ce7_native(),
        lightmapgpusolver_can_use_gpu_line_152_ffd61772_native(),
        lightmapgpusolver_ensure_line_162_a771dede_native(),
        lightmapgpusolver_solve_gpu_line_177_47133327_native(),
        lightmapgpusolver_render_direct_chunk_line_210_0fddce25_native(),
        lightmapgpusolver_tex2d_line_249_324b574b_native(),
        lightmapgpusolver_pack_lights_line_257_2f7fdace_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::gpu
