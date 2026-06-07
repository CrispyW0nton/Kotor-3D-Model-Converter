#include "GhostRiggerRuntimeSharedResources.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_runtime_shared_resources_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Runtime.Shared.Resources version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_runtime_shared_resources_capabilities_json();
    if (std::strstr(capabilities, R"("shared_runtime_resources":true)") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Resources capabilities missing shared resources flag" << std::endl;
        return 2;
    }
    if (std::strstr(gr_runtime_shared_resources_id_schema_json(), R"("schema":"runtime_resource_id.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Resources id schema mismatch" << std::endl;
        return 3;
    }
    if (std::strstr(gr_runtime_shared_resources_residency_schema_json(), R"("schema":"runtime_resource_residency.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Resources residency schema mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_runtime_shared_resources_upload_packet_schema_json(), R"("schema":"runtime_resource_upload_packet.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Resources upload schema mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_runtime_shared_resources_transition_packet_schema_json(), R"("schema":"runtime_resource_transition_packet.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Resources transition schema mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Runtime.Shared.Resources.DEBUG OK: " << version << std::endl;
    return 0;
}
