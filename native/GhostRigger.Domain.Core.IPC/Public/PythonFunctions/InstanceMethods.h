#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::ipc {

#ifndef GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ghostriggeripcserver_construct_line_59_35c0873f_native();
const NativeFunctionImplementation& ghostriggeripcserver_start_line_68_549dc037_native();
const NativeFunctionImplementation& ghostriggeripcserver_stop_line_80_3fb966f7_native();
const NativeFunctionImplementation& ghostriggeripcserver_invoke_callback_sync_line_89_d4adaccc_native();
const NativeFunctionImplementation& ghostriggeripcserver_run_server_line_113_b6c635f5_native();
const NativeFunctionImplementation& ghostriggeripcserver_schedule_callback_line_770_0f145856_native();
const NativeFunctionImplementation& ghostriggeripcserver_set_callback_line_780_92217585_native();
const NativeFunctionImplementation& ghostriggeripcserver_remove_callback_line_784_cb1e4b93_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::ipc
