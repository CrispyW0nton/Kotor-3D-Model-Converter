#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::domain::core::formats {

const NativeFunctionImplementation& gffreader_construct_line_72_dfce678b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader.__init__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader.__init__","name":"__init__","callable_type":"instance_methods","line":72,"end_line":74,"signature":{"args":["self","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffreader_parse_line_78_be205ebe_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader.parse",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader.parse","name":"parse","callable_type":"instance_methods","line":78,"end_line":140,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffreader_read_bytes_line_144_ff209d8d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader._read_bytes",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader._read_bytes","name":"_read_bytes","callable_type":"instance_methods","line":144,"end_line":147,"signature":{"args":["self","offset","count"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffreader_read_labels_line_149_ff8fb539_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader._read_labels",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader._read_labels","name":"_read_labels","callable_type":"instance_methods","line":149,"end_line":155,"signature":{"args":["self","label_off","label_cnt"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffreader_resolve_field_line_157_a03cdab8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader._resolve_field",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader._resolve_field","name":"_resolve_field","callable_type":"instance_methods","line":157,"end_line":175,"signature":{"args":["self","field_raw","labels","field_data","resolved_structs","field_inds","list_inds"],"positional_count":7,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffreader_decode_field_line_177_c72b6413_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_reader",
        "src/formats/gff_reader.py",
        "GffReader._decode_field",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"GffReader._decode_field","name":"_decode_field","callable_type":"instance_methods","line":177,"end_line":268,"signature":{"args":["self","ftype","data_or_off","field_data","resolved_structs","field_inds","list_inds"],"positional_count":7,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resref_post_construct_line_69_9f194fb8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "ResRef.__post_init__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"ResRef.__post_init__","name":"__post_init__","callable_type":"instance_methods","line":69,"end_line":71,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resref_str_line_73_bbfbb826_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "ResRef.__str__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"ResRef.__str__","name":"__str__","callable_type":"instance_methods","line":73,"end_line":74,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resref_repr_line_76_5b7f3968_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "ResRef.__repr__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"ResRef.__repr__","name":"__repr__","callable_type":"instance_methods","line":76,"end_line":77,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resref_eq_line_79_e334f978_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "ResRef.__eq__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"ResRef.__eq__","name":"__eq__","callable_type":"instance_methods","line":79,"end_line":84,"signature":{"args":["self","other"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resref_hash_line_86_5633a8af_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "ResRef.__hash__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"ResRef.__hash__","name":"__hash__","callable_type":"instance_methods","line":86,"end_line":87,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& locstring_get_text_line_108_8ae306d5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "LocString.get_text",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.get_text","name":"get_text","callable_type":"instance_methods","line":108,"end_line":110,"signature":{"args":["self","lang_id"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& locstring_set_text_line_112_f1c0b094_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "LocString.set_text",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.set_text","name":"set_text","callable_type":"instance_methods","line":112,"end_line":113,"signature":{"args":["self","text","lang_id"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& locstring_english_line_120_f21f6d63_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "LocString.english",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.english","name":"english","callable_type":"instance_methods","line":120,"end_line":121,"signature":{"args":["self","value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& locstring_repr_line_123_7eb89e36_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "LocString.__repr__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.__repr__","name":"__repr__","callable_type":"instance_methods","line":123,"end_line":128,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gfffield_repr_line_145_9db077e3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffField.__repr__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffField.__repr__","name":"__repr__","callable_type":"instance_methods","line":145,"end_line":146,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_get_line_159_ecc1ed3f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.get",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.get","name":"get","callable_type":"instance_methods","line":159,"end_line":161,"signature":{"args":["self","label","default"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_set_line_163_8310b516_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.set",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.set","name":"set","callable_type":"instance_methods","line":163,"end_line":164,"signature":{"args":["self","label","ftype","value"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_getitem_line_166_824d2507_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.__getitem__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.__getitem__","name":"__getitem__","callable_type":"instance_methods","line":166,"end_line":167,"signature":{"args":["self","label"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_setitem_line_169_1f5ee4f9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.__setitem__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.__setitem__","name":"__setitem__","callable_type":"instance_methods","line":169,"end_line":173,"signature":{"args":["self","label","value"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_contains_line_175_def2e01d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.__contains__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.__contains__","name":"__contains__","callable_type":"instance_methods","line":175,"end_line":176,"signature":{"args":["self","label"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffstruct_repr_line_178_b6d9e7ff_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffStruct.__repr__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffStruct.__repr__","name":"__repr__","callable_type":"instance_methods","line":178,"end_line":179,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gfffile_get_line_194_74808bbd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffFile.get",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffFile.get","name":"get","callable_type":"instance_methods","line":194,"end_line":195,"signature":{"args":["self","label","default"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gfffile_set_line_197_49740131_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffFile.set",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffFile.set","name":"set","callable_type":"instance_methods","line":197,"end_line":198,"signature":{"args":["self","label","ftype","value"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gfffile_repr_line_200_bfb6c7e7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_types",
        "src/formats/gff_types.py",
        "GffFile.__repr__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_types","python_file":"src/formats/gff_types.py","qualname":"GffFile.__repr__","name":"__repr__","callable_type":"instance_methods","line":200,"end_line":201,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffwriter_construct_line_47_8242ea74_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_writer",
        "src/formats/gff_writer.py",
        "GffWriter.__init__",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter.__init__","name":"__init__","callable_type":"instance_methods","line":47,"end_line":48,"signature":{"args":["self","gff"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffwriter_serialize_line_52_d944781b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_writer",
        "src/formats/gff_writer.py",
        "GffWriter.serialize",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter.serialize","name":"serialize","callable_type":"instance_methods","line":52,"end_line":200,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffwriter_encode_field_line_204_b42c6c8e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_writer",
        "src/formats/gff_writer.py",
        "GffWriter._encode_field",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter._encode_field","name":"_encode_field","callable_type":"instance_methods","line":204,"end_line":285,"signature":{"args":["self","gf","fdata","struct_idx","findices","lindices"],"positional_count":6,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gffwriter_encode_locstring_line_287_075bcc3c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Formats",
        "ghostrigger::domain::core::formats::gff_writer",
        "src/formats/gff_writer.py",
        "GffWriter._encode_locstring",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Formats","namespace":"ghostrigger::domain::core::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter._encode_locstring","name":"_encode_locstring","callable_type":"instance_methods","line":287,"end_line":299,"signature":{"args":["self","val","fdata"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gffreader_construct_line_72_dfce678b_native(),
        gffreader_parse_line_78_be205ebe_native(),
        gffreader_read_bytes_line_144_ff209d8d_native(),
        gffreader_read_labels_line_149_ff8fb539_native(),
        gffreader_resolve_field_line_157_a03cdab8_native(),
        gffreader_decode_field_line_177_c72b6413_native(),
        resref_post_construct_line_69_9f194fb8_native(),
        resref_str_line_73_bbfbb826_native(),
        resref_repr_line_76_5b7f3968_native(),
        resref_eq_line_79_e334f978_native(),
        resref_hash_line_86_5633a8af_native(),
        locstring_get_text_line_108_8ae306d5_native(),
        locstring_set_text_line_112_f1c0b094_native(),
        locstring_english_line_120_f21f6d63_native(),
        locstring_repr_line_123_7eb89e36_native(),
        gfffield_repr_line_145_9db077e3_native(),
        gffstruct_get_line_159_ecc1ed3f_native(),
        gffstruct_set_line_163_8310b516_native(),
        gffstruct_getitem_line_166_824d2507_native(),
        gffstruct_setitem_line_169_1f5ee4f9_native(),
        gffstruct_contains_line_175_def2e01d_native(),
        gffstruct_repr_line_178_b6d9e7ff_native(),
        gfffile_get_line_194_74808bbd_native(),
        gfffile_set_line_197_49740131_native(),
        gfffile_repr_line_200_bfb6c7e7_native(),
        gffwriter_construct_line_47_8242ea74_native(),
        gffwriter_serialize_line_52_d944781b_native(),
        gffwriter_encode_field_line_204_b42c6c8e_native(),
        gffwriter_encode_locstring_line_287_075bcc3c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::formats
