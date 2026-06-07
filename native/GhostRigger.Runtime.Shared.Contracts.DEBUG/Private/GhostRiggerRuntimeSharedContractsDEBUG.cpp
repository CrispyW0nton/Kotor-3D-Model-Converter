#include "GhostRiggerRuntimeSharedContracts.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_runtime_shared_contracts_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Runtime.Shared.Contracts version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_runtime_shared_contracts_capabilities_json();
    if (std::strstr(capabilities, R"("shared_runtime_contracts":true)") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Contracts capabilities missing shared runtime flag" << std::endl;
        return 2;
    }

    const char* descriptor = gr_runtime_shared_contracts_renderer_descriptor_json();
    if (std::strstr(descriptor, R"("contract":"renderer_neutral")") == nullptr) {
        std::cerr << "GhostRigger.Runtime.Shared.Contracts renderer descriptor missing neutral contract" << std::endl;
        return 3;
    }

    std::cout << "GhostRigger.Runtime.Shared.Contracts.DEBUG OK: " << version << std::endl;
    return 0;
}
