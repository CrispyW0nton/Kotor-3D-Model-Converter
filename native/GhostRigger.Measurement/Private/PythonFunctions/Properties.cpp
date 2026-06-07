#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_measurement {

const char* src_measurement_grid_measurement_gridmeasurement_major_every_line_28_7937c7aa_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Measurement","python_module":"src.measurement.grid_measurement","python_file":"src/measurement/grid_measurement.py","qualname":"GridMeasurement.major_every","name":"major_every","kind":"properties","line":28,"end_line":29,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/measurement/grid_measurement.py", "GridMeasurement.major_every", "properties", &src_measurement_grid_measurement_gridmeasurement_major_every_line_28_7937c7aa_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_measurement
