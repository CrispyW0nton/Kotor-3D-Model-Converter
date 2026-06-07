#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_special {

const char* src_core_special_lip_reader_lipshape_label_line_82_0c06e812_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Special","python_module":"src.core.special.lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPShape.label","name":"label","kind":"class_methods","line":82,"end_line":95,"signature":{"args":["cls","shape_id"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_special_lip_reader_lipshape_from_phoneme_line_98_4a5108b5_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Special","python_module":"src.core.special.lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPShape.from_phoneme","name":"from_phoneme","kind":"class_methods","line":98,"end_line":117,"signature":{"args":["cls","phoneme"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_special_lip_reader_lipfile_from_bytes_line_155_70542997_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Special","python_module":"src.core.special.lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPFile.from_bytes","name":"from_bytes","kind":"class_methods","line":155,"end_line":187,"signature":{"args":["cls","data","source_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_special_lip_reader_lipfile_from_file_line_190_1a30d4ed_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Special","python_module":"src.core.special.lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPFile.from_file","name":"from_file","kind":"class_methods","line":190,"end_line":194,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/special/lip_reader.py", "LIPShape.label", "class_methods", &src_core_special_lip_reader_lipshape_label_line_82_0c06e812_descriptor_json},
        {"src/core/special/lip_reader.py", "LIPShape.from_phoneme", "class_methods", &src_core_special_lip_reader_lipshape_from_phoneme_line_98_4a5108b5_descriptor_json},
        {"src/core/special/lip_reader.py", "LIPFile.from_bytes", "class_methods", &src_core_special_lip_reader_lipfile_from_bytes_line_155_70542997_descriptor_json},
        {"src/core/special/lip_reader.py", "LIPFile.from_file", "class_methods", &src_core_special_lip_reader_lipfile_from_file_line_190_1a30d4ed_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_special
