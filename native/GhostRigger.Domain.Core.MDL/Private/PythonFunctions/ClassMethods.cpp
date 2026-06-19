#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::domain::core::mdl {

const NativeFunctionImplementation& mdlbinaryparser_from_files_line_74_5167f1ce_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.MDL",
        "ghostrigger::domain::core::mdl::core::mdl::mdl_parser",
        "src/core/mdl/mdl_parser.py",
        "MDLBinaryParser.from_files",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.MDL","namespace":"ghostrigger::domain::core::mdl::core::mdl::mdl_parser","python_file":"src/core/mdl/mdl_parser.py","qualname":"MDLBinaryParser.from_files","name":"from_files","callable_type":"class_methods","line":74,"end_line":82,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mdlbinaryparser_parse_files_line_85_cd15af6e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.MDL",
        "ghostrigger::domain::core::mdl::core::mdl::mdl_parser",
        "src/core/mdl/mdl_parser.py",
        "MDLBinaryParser.parse_files",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.MDL","namespace":"ghostrigger::domain::core::mdl::core::mdl::mdl_parser","python_file":"src/core/mdl/mdl_parser.py","qualname":"MDLBinaryParser.parse_files","name":"parse_files","callable_type":"class_methods","line":85,"end_line":87,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.MDL",
        "ghostrigger::domain::core::mdl::core::mdl::mdl_writer",
        "src/core/mdl/mdl_writer.py",
        "MDLBinaryWriter._ensure_export_orientation_controller",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.MDL","namespace":"ghostrigger::domain::core::mdl::core::mdl::mdl_writer","python_file":"src/core/mdl/mdl_writer.py","qualname":"MDLBinaryWriter._ensure_export_orientation_controller","name":"_ensure_export_orientation_controller","callable_type":"class_methods","line":1723,"end_line":1736,"signature":{"args":["cls","node","times"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        mdlbinaryparser_from_files_line_74_5167f1ce_native(),
        mdlbinaryparser_parse_files_line_85_cd15af6e_native(),
        mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::mdl
