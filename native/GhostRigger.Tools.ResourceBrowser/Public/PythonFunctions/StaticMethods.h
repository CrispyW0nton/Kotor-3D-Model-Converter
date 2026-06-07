#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_resourcebrowser {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_resources_game_library_gamelibrary_detect_game_tag_line_815_80fc5b7b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_resourcebrowser
