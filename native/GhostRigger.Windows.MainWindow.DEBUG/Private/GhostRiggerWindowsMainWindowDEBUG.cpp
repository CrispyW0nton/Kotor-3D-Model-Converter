#include "GhostRiggerWindowsMainWindow.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_windows_main_window_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Windows.MainWindow version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_windows_main_window_capabilities_json();
    if (std::strstr(capabilities, R"("window_package":true)") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow capabilities missing window package flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("owner_surface":"Main window composition shell")") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow capabilities missing owner surface" << std::endl;
        return 3;
    }
    if (std::strstr(capabilities, R"("native_shell_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow enabled native shell too early" << std::endl;
        return 4;
    }
    if (std::strstr(gr_windows_main_window_owner_boundary_json(), R"("schema":"windows_main_window_owner_boundary.v1")") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow owner boundary mismatch" << std::endl;
        return 5;
    }
    const char* host_service_schema = gr_windows_main_window_host_service_schema_json();
    if (std::strstr(host_service_schema, R"("schema":"windows_main_window_host_service_schema.v1")") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow host service schema mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(host_service_schema, R"("host_module_registered":false)") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow registered a host module too early" << std::endl;
        return 7;
    }
    if (std::strstr(host_service_schema, R"("visible_shell_mutation_allowed":false)") == nullptr) {
        std::cerr << "GhostRigger.Windows.MainWindow allowed visible shell mutation" << std::endl;
        return 8;
    }

    std::cout << "GhostRigger.Windows.MainWindow.DEBUG OK: " << version << std::endl;
    return 0;
}
