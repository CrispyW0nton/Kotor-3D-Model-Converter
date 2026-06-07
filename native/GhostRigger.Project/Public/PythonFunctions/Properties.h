#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_project {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_project_project_validation_projectvalidationreport_has_blocking_line_47_fcc20675_descriptor_json();
const char* src_core_project_project_validation_projectvalidationreport_blocking_issues_line_51_cdb60b7e_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_project
