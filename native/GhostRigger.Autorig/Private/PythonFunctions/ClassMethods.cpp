#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_autorig {

const char* src_autorig_auto_rigger_rigtemplate_load_line_266_0f605af1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"RigTemplate.load","name":"load","kind":"class_methods","line":266,"end_line":297,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_cloth_rig_clothrigpreset_names_line_204_d261924b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.cloth_rig","python_file":"src/autorig/cloth_rig.py","qualname":"ClothRigPreset.names","name":"names","kind":"class_methods","line":204,"end_line":205,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_cloth_rig_clothrigpreset_get_line_208_148424dc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.cloth_rig","python_file":"src/autorig/cloth_rig.py","qualname":"ClothRigPreset.get","name":"get","kind":"class_methods","line":208,"end_line":214,"signature":{"args":["cls","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_retarget_engine_modelorientfixer_apply_line_181_43fa93c7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ModelOrientFixer.apply","name":"apply","kind":"class_methods","line":181,"end_line":302,"signature":{"args":["cls","model","mode","floor_snap","center_xz"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_retarget_engine_modelorientfixer_align_to_reference_line_307_f8ff80a8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ModelOrientFixer.align_to_reference","name":"align_to_reference","kind":"class_methods","line":307,"end_line":389,"signature":{"args":["cls","model","reference","match_floor","center_xy"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_retarget_engine_scalesolver_solve_line_455_84919dd2_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"ScaleSolver.solve","name":"solve","kind":"class_methods","line":455,"end_line":469,"signature":{"args":["cls","src_min","src_max","ref_min","ref_max","mode","manual_factor"],"positional_count":7,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/autorig/auto_rigger.py", "RigTemplate.load", "class_methods", &src_autorig_auto_rigger_rigtemplate_load_line_266_0f605af1_descriptor_json},
        {"src/autorig/cloth_rig.py", "ClothRigPreset.names", "class_methods", &src_autorig_cloth_rig_clothrigpreset_names_line_204_d261924b_descriptor_json},
        {"src/autorig/cloth_rig.py", "ClothRigPreset.get", "class_methods", &src_autorig_cloth_rig_clothrigpreset_get_line_208_148424dc_descriptor_json},
        {"src/autorig/retarget_engine.py", "ModelOrientFixer.apply", "class_methods", &src_autorig_retarget_engine_modelorientfixer_apply_line_181_43fa93c7_descriptor_json},
        {"src/autorig/retarget_engine.py", "ModelOrientFixer.align_to_reference", "class_methods", &src_autorig_retarget_engine_modelorientfixer_align_to_reference_line_307_f8ff80a8_descriptor_json},
        {"src/autorig/retarget_engine.py", "ScaleSolver.solve", "class_methods", &src_autorig_retarget_engine_scalesolver_solve_line_455_84919dd2_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_autorig
