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

const char* src_measurement_grid_measurement_gridmeasurement_major_every_line_28_7937c7aa_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_measurement
