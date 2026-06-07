#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_special {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_special_lip_reader_lipkeyframe_lt_line_131_797259dd_descriptor_json();
const char* src_core_special_lip_reader_lipfile_to_bytes_line_198_9f8d9982_descriptor_json();
const char* src_core_special_lip_reader_lipfile_to_file_line_213_b84e77e2_descriptor_json();
const char* src_core_special_lip_reader_lipfile_get_shapes_line_222_c8f91519_descriptor_json();
const char* src_core_special_lip_reader_lipfile_get_shape_at_time_line_266_f9399635_descriptor_json();
const char* src_core_special_lip_reader_lipfile_add_keyframe_line_276_f5b4312e_descriptor_json();
const char* src_core_special_lip_reader_lipfile_remove_keyframe_line_284_deb1089d_descriptor_json();
const char* src_core_special_lip_reader_lipfile_validate_line_295_e1e505cf_descriptor_json();
const char* src_core_special_unity_malak_smoke_unitybridgeclient_request_line_37_cd7b03b9_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_special
