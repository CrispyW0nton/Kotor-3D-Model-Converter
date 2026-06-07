#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_project {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_project_ghostrigger_project_gameinstallref_from_dict_line_60_54ec3586_descriptor_json();
const char* src_core_project_ghostrigger_project_projectassetref_from_dict_line_88_bd98ff03_descriptor_json();
const char* src_core_project_ghostrigger_project_characterjobref_from_dict_line_119_8dd1da57_descriptor_json();
const char* src_core_project_ghostrigger_project_retargetjobref_from_dict_line_161_ae4c4c41_descriptor_json();
const char* src_core_project_ghostrigger_project_moduleworkspaceref_from_dict_line_200_e0d64a02_descriptor_json();
const char* src_core_project_ghostrigger_project_mapprojectref_from_dict_line_230_4c973cf5_descriptor_json();
const char* src_core_project_ghostrigger_project_scenariopackageref_from_dict_line_263_954a9b11_descriptor_json();
const char* src_core_project_ghostrigger_project_validationsnapshotref_from_dict_line_296_7dcf1e0a_descriptor_json();
const char* src_core_project_ghostrigger_project_exportcandidateref_from_dict_line_330_5423aa04_descriptor_json();
const char* src_core_project_ghostrigger_project_ghostriggerproject_new_line_362_903b9755_descriptor_json();
const char* src_core_project_ghostrigger_project_ghostriggerproject_from_dict_line_393_e2b487ff_descriptor_json();
const char* src_core_project_resource_address_resourceaddress_from_dict_line_87_734cf9ce_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_project
