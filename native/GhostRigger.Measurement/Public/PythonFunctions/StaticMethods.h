#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_measurement {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_measurement_measurement_controller_measurementcontroller_vec3_line_95_d88715ec_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_measurement
