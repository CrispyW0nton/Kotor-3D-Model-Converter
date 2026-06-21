#pragma once

#ifdef GHOSTRIGGER_CORE_IO_FILES_EXPORTS
#define GHOSTRIGGER_CORE_IO_FILES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_IO_FILES_API __declspec(dllimport)
#endif

#include <cstddef>

extern "C" {
GHOSTRIGGER_CORE_IO_FILES_API const char* gr_core_io_files_version();
GHOSTRIGGER_CORE_IO_FILES_API const char* gr_core_io_files_capabilities_json();
GHOSTRIGGER_CORE_IO_FILES_API const char* gr_core_io_files_owner_boundary_json();
GHOSTRIGGER_CORE_IO_FILES_API const char* gr_core_io_files_dependency_schema_json();
GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_bytes(
    const char* path,
    const unsigned char* data,
    std::size_t data_size
);
GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_text_utf8(const char* path, const char* text);
}
