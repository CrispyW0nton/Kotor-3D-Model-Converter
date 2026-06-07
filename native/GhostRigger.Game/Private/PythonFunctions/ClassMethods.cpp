#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_game {

const char* src_core_game_game_library_ext_gffreader_from_bytes_line_256_55910253_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.game_library_ext","python_file":"src/core/game/game_library_ext.py","qualname":"GFFReader.from_bytes","name":"from_bytes","kind":"class_methods","line":256,"end_line":266,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/game/game_library_ext.py", "GFFReader.from_bytes", "class_methods", &src_core_game_game_library_ext_gffreader_from_bytes_line_256_55910253_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_game
