#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_measurement {

const char* src_measurement_unit_settings_measurementsettings_from_dict_line_28_fa44741f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"MeasurementSettings.from_dict","name":"from_dict","kind":"class_methods","line":28,"end_line":54,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/measurement/unit_settings.py", "MeasurementSettings.from_dict", "class_methods", &src_measurement_unit_settings_measurementsettings_from_dict_line_28_fa44741f_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_measurement
