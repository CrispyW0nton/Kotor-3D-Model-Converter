#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_twodabrowser {

const char* src_core_game_game_library_ext_gffreader_from_bytes_line_256_55910253_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.TwoDABrowser","python_module":"src.core.game.game_library_ext","python_file":"src/core/game/game_library_ext.py","qualname":"GFFReader.from_bytes","name":"from_bytes","kind":"class_methods","line":256,"end_line":266,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_templates_twoda_twoda_from_bytes_line_88_45af8178_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.TwoDABrowser","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA.from_bytes","name":"from_bytes","kind":"class_methods","line":88,"end_line":100,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_templates_twoda_twoda_from_file_line_103_aca436e4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.TwoDABrowser","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA.from_file","name":"from_file","kind":"class_methods","line":103,"end_line":109,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_templates_twoda_twoda_parse_binary_line_114_bc648710_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.TwoDABrowser","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA._parse_binary","name":"_parse_binary","kind":"class_methods","line":114,"end_line":195,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_templates_twoda_twoda_parse_ascii_line_200_d1371498_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.TwoDABrowser","python_module":"src.core.templates.twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA._parse_ascii","name":"_parse_ascii","kind":"class_methods","line":200,"end_line":237,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/game/game_library_ext.py", "GFFReader.from_bytes", "class_methods", &src_core_game_game_library_ext_gffreader_from_bytes_line_256_55910253_descriptor_json},
        {"src/core/templates/twoda.py", "TwoDA.from_bytes", "class_methods", &src_core_templates_twoda_twoda_from_bytes_line_88_45af8178_descriptor_json},
        {"src/core/templates/twoda.py", "TwoDA.from_file", "class_methods", &src_core_templates_twoda_twoda_from_file_line_103_aca436e4_descriptor_json},
        {"src/core/templates/twoda.py", "TwoDA._parse_binary", "class_methods", &src_core_templates_twoda_twoda_parse_binary_line_114_bc648710_descriptor_json},
        {"src/core/templates/twoda.py", "TwoDA._parse_ascii", "class_methods", &src_core_templates_twoda_twoda_parse_ascii_line_200_d1371498_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_twodabrowser
