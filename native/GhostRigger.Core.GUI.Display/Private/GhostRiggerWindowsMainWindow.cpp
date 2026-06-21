#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerWindowsMainWindow.h"

#include <atomic>
#include <sstream>
#include <thread>
#include <vector>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"windows_main_window_owner_boundary.v1",)"
    R"("window_package":"GhostRigger.Core.GUI.Display",)"
    R"("owner_surface":"Main window composition shell",)"
    R"("owner_package":"native/GhostRigger.Core.GUI.Display",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["host_service_discovery_metadata","native_command_routing_metadata","application_shell_diagnostics"],)"
    R"("python_owns":["qt_widgets","docks","menus","themes","layouts","window_state","user_workflow_orchestration"],)"
    R"("native_shell_enabled":false})";
constexpr const char* kHostServiceSchema =
    R"({"schema":"windows_main_window_host_service_schema.v1",)"
    R"("window_package":"GhostRigger.Core.GUI.Display",)"
    R"("diagnostic_only":true,)"
    R"("native_shell_enabled":false,)"
    R"("service_packets":["host_service_registry","native_command_route","shell_diagnostic_record","startup_bridge_status"],)"
    R"("host_module_registered":false,"service_count":0,)"
    R"("visible_shell_mutation_allowed":false,)"
    R"("failure_points":["host_module_missing","python_shell_owner_active","native_shell_disabled","service_registry_empty"]})";

void emit_prelaunch_status(
    GRWindowsMainPrelaunchStatusCallback status_callback,
    const char* title,
    const char* detail
) {
    if (status_callback != nullptr) {
        status_callback(title, detail);
    }
}

} // namespace

extern "C" {

GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_version() {
    return kVersion;
}

GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_capabilities_json() {
    return R"({"name":"GhostRigger.Core.GUI.Display","version":"0.1.0",)"
           R"("phase":"P1 foundation","window_package":true,)"
           R"("owner_surface":"Main window composition shell",)"
           R"("bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_shell_enabled":false,)"
           R"("capabilities":["owner_boundary","host_service_schema","shell_diagnostics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_host_service_schema_json() {
    return kHostServiceSchema;
}

GR_WINDOWS_MAIN_WINDOW_API int gr_windows_main_window_run_prelaunch_tasks(
    int task_count,
    GRWindowsMainPrelaunchTaskCallback task_callback,
    GRWindowsMainPrelaunchStatusCallback status_callback
) {
    if (task_callback == nullptr) {
        emit_prelaunch_status(status_callback, "Native startup threading unavailable", "No pre-launch task callback was provided.");
        return 1;
    }
    if (task_count <= 0) {
        emit_prelaunch_status(status_callback, "Native startup threading", "No pre-launch work was scheduled.");
        return 0;
    }

    const int clamped_task_count = task_count > 8 ? 8 : task_count;
    std::atomic<int> completed_tasks{0};
    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(clamped_task_count));
    emit_prelaunch_status(
        status_callback,
        "Native startup threading",
        "Scheduling pre-launch diagnostics and library preparation on C++ worker threads."
    );

    for (int task_index = 0; task_index < clamped_task_count; ++task_index) {
        workers.emplace_back([task_index, task_callback, status_callback, &completed_tasks, clamped_task_count]() {
            {
                std::ostringstream detail;
                detail << "C++ worker " << (task_index + 1) << " started.";
                emit_prelaunch_status(status_callback, "Pre-launch worker started", detail.str().c_str());
            }

            task_callback(task_index);

            const int finished = ++completed_tasks;
            std::ostringstream detail;
            detail << finished << " of " << clamped_task_count << " native pre-launch workers finished.";
            emit_prelaunch_status(status_callback, "Pre-launch worker finished", detail.str().c_str());
        });
    }

    for (std::thread& worker : workers) {
        if (worker.joinable()) {
            worker.join();
        }
    }

    emit_prelaunch_status(status_callback, "Native startup threading ready", "C++ pre-launch workers completed.");
    return 0;
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
