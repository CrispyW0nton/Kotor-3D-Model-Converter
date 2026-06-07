#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_ipc {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_ipc_server_ghostriggeripcserver_init_line_59_35c0873f_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_start_line_68_549dc037_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_stop_line_80_3fb966f7_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_invoke_callback_sync_line_89_d4adaccc_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_run_server_line_113_b6c635f5_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_schedule_callback_line_770_0f145856_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_set_callback_line_780_92217585_descriptor_json();
const char* src_ipc_server_ghostriggeripcserver_remove_callback_line_784_cb1e4b93_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_ipc
