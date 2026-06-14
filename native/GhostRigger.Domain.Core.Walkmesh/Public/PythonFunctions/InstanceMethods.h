#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::walkmesh {

#ifndef GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& walkmeshoverlay_construct_line_187_29d6a454_native();
const NativeFunctionImplementation& walkmeshoverlay_load_from_wok_line_195_a0d500bd_native();
const NativeFunctionImplementation& walkmeshoverlay_load_from_ascii_wok_line_235_745fcb2c_native();
const NativeFunctionImplementation& walkmeshoverlay_walkable_faces_line_289_b33a2e47_native();
const NativeFunctionImplementation& walkmeshoverlay_non_walkable_faces_line_292_4c0ce679_native();
const NativeFunctionImplementation& walkmeshoverlay_faces_by_material_line_295_e834cd8f_native();
const NativeFunctionImplementation& walkmeshoverlay_faces_for_render_line_298_3728a6b1_native();
const NativeFunctionImplementation& walkmeshoverlay_aabb_line_314_82c0207c_native();
const NativeFunctionImplementation& walkmeshoverlay_summary_line_331_2ae230ef_native();
const NativeFunctionImplementation& walkmeshoverlay_boundary_edges_line_340_1a989b1a_native();
const NativeFunctionImplementation& walkmeshloader_from_wok_data_line_395_af5b94d6_native();
const NativeFunctionImplementation& walkmeshloader_from_file_line_402_9cc0fc61_native();
const NativeFunctionImplementation& walkmeshloader_from_scene_room_line_416_cadddf33_native();
const NativeFunctionImplementation& walkmeshloader_load_all_room_overlays_line_426_7a60ecf0_native();
const NativeFunctionImplementation& walkmeshwriter_to_bytes_line_523_6069c2fb_native();
const NativeFunctionImplementation& walkmeshwriter_to_bytes_from_wok_line_535_90912352_native();
const NativeFunctionImplementation& walkmeshwriter_write_file_line_545_14bbad56_native();
const NativeFunctionImplementation& walkmeshwriter_write_wok_file_line_557_a80a0a68_native();
const NativeFunctionImplementation& walkmeshwriter_extract_geometry_line_586_38a9d751_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_construct_line_743_55186ffc_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_visible_line_758_2d38d64c_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_toggle_line_762_3c2bbce5_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_on_key_line_773_f67fe1bf_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_toggle_room_line_786_5eecdb22_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_set_all_line_799_9b83b04b_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_set_overlays_line_804_de6a3441_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_set_key_line_809_2771a18a_native();
const NativeFunctionImplementation& walkmeshtogglecontroller_sync_overlays_line_825_72803aef_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::walkmesh
