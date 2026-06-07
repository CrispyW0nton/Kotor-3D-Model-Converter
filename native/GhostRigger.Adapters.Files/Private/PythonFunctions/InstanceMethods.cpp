#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_adapters_files {

const char* src_adapters_files_local_file_writer_localfilewriter_write_bytes_line_15_ad2c205d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.Files","python_module":"src.adapters.files.local_file_writer","python_file":"src/adapters/files/local_file_writer.py","qualname":"LocalFileWriter.write_bytes","name":"write_bytes","kind":"instance_methods","line":15,"end_line":18,"signature":{"args":["self","path","data"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_files_local_file_writer_localfilewriter_write_text_line_20_ec441b06_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.Files","python_module":"src.adapters.files.local_file_writer","python_file":"src/adapters/files/local_file_writer.py","qualname":"LocalFileWriter.write_text","name":"write_text","kind":"instance_methods","line":20,"end_line":23,"signature":{"args":["self","path","text","encoding"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/files/local_file_writer.py", "LocalFileWriter.write_bytes", "instance_methods", &src_adapters_files_local_file_writer_localfilewriter_write_bytes_line_15_ad2c205d_descriptor_json},
        {"src/adapters/files/local_file_writer.py", "LocalFileWriter.write_text", "instance_methods", &src_adapters_files_local_file_writer_localfilewriter_write_text_line_20_ec441b06_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_files
