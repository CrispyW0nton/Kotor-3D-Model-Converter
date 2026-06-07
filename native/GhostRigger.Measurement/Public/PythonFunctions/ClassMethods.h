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

const char* src_measurement_unit_settings_measurementsettings_from_dict_line_28_fa44741f_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_measurement
