#pragma once

#include <cstdint>

#if defined(_WIN32)
#if defined(NATIVE_CORE_EXPORTS)
#define GR_NATIVE_CORE_API __declspec(dllexport)
#else
#define GR_NATIVE_CORE_API __declspec(dllimport)
#endif
#else
#define GR_NATIVE_CORE_API
#endif

extern "C" {

GR_NATIVE_CORE_API const char* gr_native_core_version();
GR_NATIVE_CORE_API const char* gr_native_core_capabilities_json();

GR_NATIVE_CORE_API void* gr_native_core_create_handle_allocator();
GR_NATIVE_CORE_API void gr_native_core_destroy_handle_allocator(void* allocator);
GR_NATIVE_CORE_API void gr_native_core_reset_handle_allocator(void* allocator);
GR_NATIVE_CORE_API std::uint64_t gr_native_core_allocate_handle(void* allocator);
GR_NATIVE_CORE_API std::uint64_t gr_native_core_last_handle(void* allocator);

}
