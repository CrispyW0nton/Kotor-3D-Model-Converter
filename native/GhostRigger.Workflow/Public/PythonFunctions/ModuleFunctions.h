#pragma once

#include <cstddef>

namespace ghostrigger::workflow {

#ifndef GHOSTRIGGER_WORKFLOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WORKFLOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WORKFLOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& import_model_data_line_82_3c6c0659_native();
const NativeFunctionImplementation& import_validation_service_line_96_7fff170e_native();
const NativeFunctionImplementation& import_accurig_line_105_b9ea3e7c_native();
const NativeFunctionImplementation& import_scene_io_line_118_2de54ed5_native();
const NativeFunctionImplementation& summarize_issues_line_153_7ba076da_native();
const NativeFunctionImplementation& blocking_codes_from_issues_line_208_6ada9ff5_native();
const NativeFunctionImplementation& ext_of_line_339_896772f2_native();
const NativeFunctionImplementation& resref_from_path_line_345_c25e7d68_native();
const NativeFunctionImplementation& safe_resref_line_355_4741b6fb_native();
const NativeFunctionImplementation& import_model_data_line_53_bd1d3466_native();
const NativeFunctionImplementation& import_body_workflow_line_61_26f6848f_native();
const NativeFunctionImplementation& import_head_workflow_line_69_194f4fc3_native();
const NativeFunctionImplementation& import_character_builder_line_77_f52d5677_native();
const NativeFunctionImplementation& import_validation_service_line_85_e7f5da99_native();
const NativeFunctionImplementation& import_workflow_base_line_93_506cb17a_native();
const NativeFunctionImplementation& import_creature_appearance_line_101_7c2a6fe6_native();
const NativeFunctionImplementation& import_scene_io_line_109_1a650e6c_native();
const NativeFunctionImplementation& import_mesh_exporters_line_117_2600da03_native();
const NativeFunctionImplementation& slot_models_line_210_ca8fcfa9_native();
const NativeFunctionImplementation& make_issue_line_217_44ee55cf_native();
const NativeFunctionImplementation& normalise_quat_line_233_e158161d_native();
const NativeFunctionImplementation& matrix_from_transform_line_241_6ec8e7a8_native();
const NativeFunctionImplementation& first_root_name_line_260_cd65a3ed_native();
const NativeFunctionImplementation& write_snap_metadata_line_273_afb48ac3_native();
const NativeFunctionImplementation& supermodel_value_line_297_b1347312_native();
const NativeFunctionImplementation& bounds_line_301_3d513d35_native();
const NativeFunctionImplementation& append_supermodel_issues_line_323_8a3a2e3d_native();
const NativeFunctionImplementation& append_seam_issue_line_363_e5fc4668_native();
const NativeFunctionImplementation& snap_head_to_body_line_399_f26a7c73_native();
const NativeFunctionImplementation& load_composite_line_490_12045c43_native();
const NativeFunctionImplementation& check_composite_line_559_2a2767b8_native();
const NativeFunctionImplementation& update_snap_after_scene_mutation_line_621_3a421500_native();
const NativeFunctionImplementation& scene_resref_line_635_8368a739_native();
const NativeFunctionImplementation& composite_export_model_line_653_20db1318_native();
const NativeFunctionImplementation& export_composite_single_format_line_679_1eee98f5_native();
const NativeFunctionImplementation& export_composite_scene_line_734_cd23b5b0_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::workflow
