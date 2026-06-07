#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_measurement {

const char* src_measurement_dimension_calculator_quat_to_euler_degrees_line_23_8759ec24_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.dimension_calculator","python_file":"src/measurement/dimension_calculator.py","qualname":"_quat_to_euler_degrees","name":"_quat_to_euler_degrees","kind":"module_functions","line":23,"end_line":40,"signature":{"args":["q"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_measurement_unit_settings_load_measurement_settings_line_73_ed98c203_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"load_measurement_settings","name":"load_measurement_settings","kind":"module_functions","line":73,"end_line":79,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_measurement_unit_settings_save_measurement_settings_line_82_f5bf0fc4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"save_measurement_settings","name":"save_measurement_settings","kind":"module_functions","line":82,"end_line":84,"signature":{"args":["path","settings"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_measurement_unit_system_normalize_unit_line_96_2c3e73d5_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.unit_system","python_file":"src/measurement/unit_system.py","qualname":"normalize_unit","name":"normalize_unit","kind":"module_functions","line":96,"end_line":102,"signature":{"args":["unit_name","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/measurement/dimension_calculator.py", "_quat_to_euler_degrees", "module_functions", &src_measurement_dimension_calculator_quat_to_euler_degrees_line_23_8759ec24_descriptor_json},
        {"src/measurement/unit_settings.py", "load_measurement_settings", "module_functions", &src_measurement_unit_settings_load_measurement_settings_line_73_ed98c203_descriptor_json},
        {"src/measurement/unit_settings.py", "save_measurement_settings", "module_functions", &src_measurement_unit_settings_save_measurement_settings_line_82_f5bf0fc4_descriptor_json},
        {"src/measurement/unit_system.py", "normalize_unit", "module_functions", &src_measurement_unit_system_normalize_unit_line_96_2c3e73d5_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_measurement
