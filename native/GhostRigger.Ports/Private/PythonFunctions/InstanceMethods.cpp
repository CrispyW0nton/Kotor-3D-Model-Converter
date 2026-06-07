#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_ports {

const char* src_core_ports_files_filewriterport_write_bytes_line_13_386e4596_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Ports","python_module":"src.core.ports.files","python_file":"src/core/ports/files.py","qualname":"FileWriterPort.write_bytes","name":"write_bytes","kind":"instance_methods","line":13,"end_line":14,"signature":{"args":["self","path","data"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_ports_files_filewriterport_write_text_line_16_f4a4863f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Ports","python_module":"src.core.ports.files","python_file":"src/core/ports/files.py","qualname":"FileWriterPort.write_text","name":"write_text","kind":"instance_methods","line":16,"end_line":17,"signature":{"args":["self","path","text","encoding"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_ports_scripts_scriptcompilerport_compile_script_line_27_6df94b86_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Ports","python_module":"src.core.ports.scripts","python_file":"src/core/ports/scripts.py","qualname":"ScriptCompilerPort.compile_script","name":"compile_script","kind":"instance_methods","line":27,"end_line":28,"signature":{"args":["self","source","game"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_ports_textures_texturedecoder_decode_texture_line_27_e83bd02c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Ports","python_module":"src.core.ports.textures","python_file":"src/core/ports/textures.py","qualname":"TextureDecoder.decode_texture","name":"decode_texture","kind":"instance_methods","line":27,"end_line":34,"signature":{"args":["self","data","name","source"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/ports/files.py", "FileWriterPort.write_bytes", "instance_methods", &src_core_ports_files_filewriterport_write_bytes_line_13_386e4596_descriptor_json},
        {"src/core/ports/files.py", "FileWriterPort.write_text", "instance_methods", &src_core_ports_files_filewriterport_write_text_line_16_f4a4863f_descriptor_json},
        {"src/core/ports/scripts.py", "ScriptCompilerPort.compile_script", "instance_methods", &src_core_ports_scripts_scriptcompilerport_compile_script_line_27_6df94b86_descriptor_json},
        {"src/core/ports/textures.py", "TextureDecoder.decode_texture", "instance_methods", &src_core_ports_textures_texturedecoder_decode_texture_line_27_e83bd02c_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_ports
