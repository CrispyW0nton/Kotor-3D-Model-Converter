#pragma once

#include "GhostRiggerCoreIOFiles.h"

#include <cstddef>
#include <string>

namespace ghostrigger::core::io::files::local_file_writer {

bool write_bytes(const std::string& path, const unsigned char* data, std::size_t data_size);
bool write_text_utf8(const std::string& path, const std::string& text);
bool write_text(
    const std::string& path,
    const std::string& text,
    const std::string& encoding
);

} // namespace ghostrigger::core::io::files::local_file_writer

extern "C" {

GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_bytes(
    const char* path,
    const unsigned char* data,
    std::size_t data_size
);

GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_text_utf8(
    const char* path,
    const char* text
);
GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_text(
    const char* path,
    const char* text,
    const char* encoding
);

}
