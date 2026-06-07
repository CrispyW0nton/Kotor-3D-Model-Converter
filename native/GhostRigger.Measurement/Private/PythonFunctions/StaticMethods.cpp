#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_measurement {

const char* src_measurement_measurement_controller_measurementcontroller_vec3_line_95_d88715ec_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.measurement_controller","python_file":"src/measurement/measurement_controller.py","qualname":"MeasurementController._vec3","name":"_vec3","kind":"static_methods","line":95,"end_line":96,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/measurement/measurement_controller.py", "MeasurementController._vec3", "static_methods", &src_measurement_measurement_controller_measurementcontroller_vec3_line_95_d88715ec_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_measurement
