#include "GhostRigger.Native.NativeCore.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Native.NativeCore","version":"0.1.0","phase":"P1 foundation",)"
    R"("shared_handles":true,"diagnostic_contracts":true,"renderer_neutral":true})";

struct HandleAllocator {
    std::uint64_t next_handle = 1;
    std::uint64_t last_handle = 0;
};

HandleAllocator* allocator_from_handle(void* handle) {
    return static_cast<HandleAllocator*>(handle);
}

} // namespace

extern "C" {

GR_NATIVE_CORE_API const char* gr_native_core_version() {
    return kVersion;
}

GR_NATIVE_CORE_API const char* gr_native_core_capabilities_json() {
    return kCapabilities;
}

GR_NATIVE_CORE_API void* gr_native_core_create_handle_allocator() {
    return new HandleAllocator{};
}

GR_NATIVE_CORE_API void gr_native_core_destroy_handle_allocator(void* allocator) {
    delete allocator_from_handle(allocator);
}

GR_NATIVE_CORE_API void gr_native_core_reset_handle_allocator(void* allocator) {
    auto* target = allocator_from_handle(allocator);
    if (target == nullptr) {
        return;
    }
    target->next_handle = 1;
    target->last_handle = 0;
}

GR_NATIVE_CORE_API std::uint64_t gr_native_core_allocate_handle(void* allocator) {
    auto* target = allocator_from_handle(allocator);
    if (target == nullptr) {
        return 0;
    }
    target->last_handle = target->next_handle;
    target->next_handle += 1;
    return target->last_handle;
}

GR_NATIVE_CORE_API std::uint64_t gr_native_core_last_handle(void* allocator) {
    const auto* target = allocator_from_handle(allocator);
    if (target == nullptr) {
        return 0;
    }
    return target->last_handle;
}

}
