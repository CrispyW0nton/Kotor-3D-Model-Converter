#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerWorkflow.h"
#include "WorkflowBase.h"

#include <cstring>
#include <string>

namespace workflow_base = ghostrigger::core::workflow::core::workflow::workflow_base;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"workflow_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Workflow",)"
    R"("source_package":"src/core/workflow",)"
    R"("owner_surface":"Workflow orchestration",)"
    R"("owner_package":"native/GhostRigger.Core.Workflow",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","workflow_base_path_helpers","workflow_base_summary_helpers"],)"
    R"("python_owns":["lazy_import_shims","workflow_dataclasses","python_object_issue_summarization","workflow_policy","ui_state"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"workflow_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Workflow",)"
    R"("source_package":"src/core/workflow",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_workflow_base_scope":"path_and_count_summary_helpers"})";

int write_output(const std::string& value, char* output, unsigned long long output_size) {
    const int required = static_cast<int>(value.size() + 1);
    if (output == nullptr || output_size == 0) {
        return required;
    }
    const unsigned long long copy_size = output_size - 1;
    const unsigned long long wanted = value.size() < copy_size ? value.size() : copy_size;
    if (wanted > 0) {
        std::memcpy(output, value.data(), static_cast<std::size_t>(wanted));
    }
    output[wanted] = '\0';
    return required;
}

} // namespace

extern "C" {

GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_version() {
    return kVersion;
}

GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Workflow","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/workflow",)"
           R"("owner_surface":"Workflow orchestration","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","workflow_base_path_helpers","workflow_base_summary_helpers"],)"
           R"("native_scope":"workflow_base path and count-summary helpers",)"
           R"("python_fallback_reason":"workflow dataclasses, lazy imports, and Python object issue inspection remain Python-owned until their callers are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_ext_of(const char* path, char* output, unsigned long long output_size) {
    return write_output(workflow_base::ext_of(path == nullptr ? "" : path), output, output_size);
}

GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_resref_from_path(
    const char* path,
    char* output,
    unsigned long long output_size
) {
    return write_output(workflow_base::resref_from_path(path == nullptr ? "" : path), output, output_size);
}

GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_safe_resref(
    const char* text,
    const char* fallback,
    char* output,
    unsigned long long output_size
) {
    return write_output(
        workflow_base::safe_resref(text == nullptr ? "" : text, fallback == nullptr ? "untitled" : fallback),
        output,
        output_size
    );
}

GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_banner_key_for_counts(
    int errors,
    int warnings,
    int infos,
    char* output,
    unsigned long long output_size
) {
    return write_output(workflow_base::banner_key_for_counts(errors, warnings, infos), output, output_size);
}

GHOSTRIGGER_WORKFLOW_API int gr_workflow_base_summary_for_counts(
    int errors,
    int warnings,
    int infos,
    char* output,
    unsigned long long output_size
) {
    return write_output(workflow_base::summary_for_counts(errors, warnings, infos), output, output_size);
}

GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_base_schema_json() {
    return workflow_base::workflow_base_schema_json();
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
