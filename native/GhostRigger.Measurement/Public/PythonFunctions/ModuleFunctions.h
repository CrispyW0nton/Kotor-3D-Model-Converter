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

const char* src_measurement_dimension_calculator_quat_to_euler_degrees_line_23_8759ec24_descriptor_json();
const char* src_measurement_unit_settings_load_measurement_settings_line_73_ed98c203_descriptor_json();
const char* src_measurement_unit_settings_save_measurement_settings_line_82_f5bf0fc4_descriptor_json();
const char* src_measurement_unit_system_normalize_unit_line_96_2c3e73d5_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_measurement
