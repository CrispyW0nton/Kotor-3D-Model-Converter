#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols {

const char* src_core_gizmo_transform_controller_transformcontroller_tuple_attr_line_77_8f25bbb8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.PivotControls","python_module":"src.core.gizmo.transform_controller","python_file":"src/core/gizmo/transform_controller.py","qualname":"TransformController._tuple_attr","name":"_tuple_attr","kind":"static_methods","line":77,"end_line":84,"signature":{"args":["obj","name","fallback","count"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/gizmo/transform_controller.py", "TransformController._tuple_attr", "static_methods", &src_core_gizmo_transform_controller_transformcontroller_tuple_attr_line_77_8f25bbb8_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
