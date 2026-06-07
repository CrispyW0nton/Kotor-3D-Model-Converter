#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_gamelibrary {

const char* src_resources_game_library_resourceentry_is_model_line_148_43c8a66b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ResourceEntry.is_model","name":"is_model","kind":"properties","line":148,"end_line":155,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_resources_game_library_resourceentry_is_texture_line_158_fe34306f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ResourceEntry.is_texture","name":"is_texture","kind":"properties","line":158,"end_line":173,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_resources_game_library_resourceentry_ext_line_176_0604481f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ResourceEntry.ext","name":"ext","kind":"properties","line":176,"end_line":180,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_resources_game_library_resourceentry_filename_line_183_c3d15313_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ResourceEntry.filename","name":"filename","kind":"properties","line":183,"end_line":184,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_resources_game_library_modellibraryentry_display_label_line_564_bd018b8d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ModelLibraryEntry.display_label","name":"display_label","kind":"properties","line":564,"end_line":569,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_resources_game_library_modellibraryentry_display_label_rich_line_572_ec474d1b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GameLibrary","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"ModelLibraryEntry.display_label_rich","name":"display_label_rich","kind":"properties","line":572,"end_line":657,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/resources/game_library.py", "ResourceEntry.is_model", "properties", &src_resources_game_library_resourceentry_is_model_line_148_43c8a66b_descriptor_json},
        {"src/resources/game_library.py", "ResourceEntry.is_texture", "properties", &src_resources_game_library_resourceentry_is_texture_line_158_fe34306f_descriptor_json},
        {"src/resources/game_library.py", "ResourceEntry.ext", "properties", &src_resources_game_library_resourceentry_ext_line_176_0604481f_descriptor_json},
        {"src/resources/game_library.py", "ResourceEntry.filename", "properties", &src_resources_game_library_resourceentry_filename_line_183_c3d15313_descriptor_json},
        {"src/resources/game_library.py", "ModelLibraryEntry.display_label", "properties", &src_resources_game_library_modellibraryentry_display_label_line_564_bd018b8d_descriptor_json},
        {"src/resources/game_library.py", "ModelLibraryEntry.display_label_rich", "properties", &src_resources_game_library_modellibraryentry_display_label_rich_line_572_ec474d1b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gamelibrary
