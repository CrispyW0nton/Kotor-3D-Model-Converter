#include "GhostRigger.Native.NativeCore.h"

#include <cstring>
#include <iostream>

int main() {
    const char* version = gr_native_core_version();
    if (version == nullptr || std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Native.NativeCore version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_native_core_capabilities_json();
    if (capabilities == nullptr || std::strstr(capabilities, "shared_handles") == nullptr) {
        std::cerr << "GhostRigger.Native.NativeCore capabilities missing shared_handles" << std::endl;
        return 2;
    }

    void* allocator = gr_native_core_create_handle_allocator();
    if (allocator == nullptr) {
        std::cerr << "Handle allocator creation failed" << std::endl;
        return 3;
    }

    const auto first = gr_native_core_allocate_handle(allocator);
    const auto second = gr_native_core_allocate_handle(allocator);
    if (first != 1 || second != 2 || gr_native_core_last_handle(allocator) != 2) {
        gr_native_core_destroy_handle_allocator(allocator);
        std::cerr << "Handle allocator sequence failed" << std::endl;
        return 4;
    }

    gr_native_core_reset_handle_allocator(allocator);
    if (gr_native_core_last_handle(allocator) != 0 || gr_native_core_allocate_handle(allocator) != 1) {
        gr_native_core_destroy_handle_allocator(allocator);
        std::cerr << "Handle allocator reset failed" << std::endl;
        return 5;
    }

    gr_native_core_destroy_handle_allocator(allocator);
    std::cout << "GhostRigger.Native.NativeCore.DEBUG OK: " << version << std::endl;
    return 0;
}
