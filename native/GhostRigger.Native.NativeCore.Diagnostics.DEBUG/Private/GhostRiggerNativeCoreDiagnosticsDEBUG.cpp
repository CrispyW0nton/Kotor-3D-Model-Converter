#include "GhostRiggerNativeCoreDiagnostics.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_native_core_diagnostics_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Native.NativeCore.Diagnostics version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_native_core_diagnostics_capabilities_json();
    if (std::strstr(capabilities, R"("shared_diagnostics":true)") == nullptr) {
        std::cerr << "GhostRigger.Native.NativeCore.Diagnostics capabilities missing shared diagnostics flag" << std::endl;
        return 2;
    }

    const char* schema = gr_native_core_diagnostics_record_schema_json();
    if (std::strstr(schema, R"("schema":"native_diagnostic_record.v1")") == nullptr) {
        std::cerr << "GhostRigger.Native.NativeCore.Diagnostics schema missing record version" << std::endl;
        return 3;
    }

    const char* record = gr_native_core_diagnostics_make_record_json(
        2,
        "GhostRigger.Runtime",
        "phase1.debug",
        "Diagnostics bridge ready");
    if (std::strstr(record, R"("severity":2)") == nullptr ||
        std::strstr(record, R"("system":"GhostRigger.Runtime")") == nullptr ||
        std::strstr(record, R"("code":"phase1.debug")") == nullptr) {
        std::cerr << "GhostRigger.Native.NativeCore.Diagnostics record payload did not round-trip" << std::endl;
        return 4;
    }

    std::cout << "GhostRigger.Native.NativeCore.Diagnostics.DEBUG OK: " << version << std::endl;
    return 0;
}
