#include "GhostRiggerRuntimeSharedDescriptors.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_runtime_shared_descriptors_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Runtime.Shared.Descriptors version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_runtime_shared_descriptors_capabilities_json();
    if (std::strstr(capabilities, R"("shared_runtime_descriptors":true)") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Descriptors capabilities missing shared descriptor flag" << std::endl;
        return 2;
    }

    if (std::strstr(gr_runtime_shared_descriptors_mesh_schema_json(), R"("schema":"runtime_mesh_descriptor.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Descriptors mesh schema mismatch" << std::endl;
        return 3;
    }
    if (std::strstr(gr_runtime_shared_descriptors_material_schema_json(), R"("schema":"runtime_material_descriptor.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Descriptors material schema mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_runtime_shared_descriptors_frame_schema_json(), R"("schema":"runtime_frame_descriptor.v1")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Descriptors frame schema mismatch" << std::endl;
        return 5;
    }

    std::cout << "GhostRigger.Runtime.Shared.Descriptors.DEBUG OK: " << version << std::endl;
    return 0;
}
