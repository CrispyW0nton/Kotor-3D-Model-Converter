#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_sequence {

const char* src_sequence_sequence_manager_sequencemanager_safe_filename_line_174_6e8e07fc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Sequence","python_module":"src.sequence.sequence_manager","python_file":"src/sequence/sequence_manager.py","qualname":"SequenceManager.safe_filename","name":"safe_filename","kind":"static_methods","line":174,"end_line":177,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/sequence/sequence_manager.py", "SequenceManager.safe_filename", "static_methods", &src_sequence_sequence_manager_sequencemanager_safe_filename_line_174_6e8e07fc_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_sequence
