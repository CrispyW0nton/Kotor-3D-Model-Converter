#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_ports {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_ports_files_filewriterport_write_bytes_line_13_386e4596_descriptor_json();
const char* src_core_ports_files_filewriterport_write_text_line_16_f4a4863f_descriptor_json();
const char* src_core_ports_scripts_scriptcompilerport_compile_script_line_27_6df94b86_descriptor_json();
const char* src_core_ports_textures_texturedecoder_decode_texture_line_27_e83bd02c_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_ports
