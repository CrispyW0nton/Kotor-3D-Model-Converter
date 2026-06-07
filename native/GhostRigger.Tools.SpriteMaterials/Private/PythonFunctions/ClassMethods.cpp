#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_spritematerials {

const char* src_sequence_tracks_material_track_materialtrack_deserialize_line_51_ed9b85b8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SpriteMaterials","python_module":"src.sequence.tracks.material_track","python_file":"src/sequence/tracks/material_track.py","qualname":"MaterialTrack.deserialize","name":"deserialize","kind":"class_methods","line":51,"end_line":66,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/sequence/tracks/material_track.py", "MaterialTrack.deserialize", "class_methods", &src_sequence_tracks_material_track_materialtrack_deserialize_line_51_ed9b85b8_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_spritematerials
