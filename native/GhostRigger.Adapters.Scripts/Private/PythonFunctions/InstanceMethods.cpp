#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_adapters_scripts {

const char* src_adapters_scripts_unavailable_compiler_unavailablescriptcompiler_compile_script_line_29_00747c15_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.Scripts","python_module":"src.adapters.scripts.unavailable_compiler","python_file":"src/adapters/scripts/unavailable_compiler.py","qualname":"UnavailableScriptCompiler.compile_script","name":"compile_script","kind":"instance_methods","line":29,"end_line":46,"signature":{"args":["self","source","game"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/scripts/unavailable_compiler.py", "UnavailableScriptCompiler.compile_script", "instance_methods", &src_adapters_scripts_unavailable_compiler_unavailablescriptcompiler_compile_script_line_29_00747c15_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_scripts
