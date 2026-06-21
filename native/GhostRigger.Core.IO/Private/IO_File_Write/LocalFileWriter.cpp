#include "IO_File_Write/LocalFileWriter.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>

namespace ghostrigger::core::io::files::local_file_writer {
namespace {

bool ensure_parent_directory(const std::filesystem::path& target) {
    const std::filesystem::path parent = target.parent_path();
    if (parent.empty()) {
        return true;
    }
    std::error_code error;
    std::filesystem::create_directories(parent, error);
    return !error;
}

} // namespace

bool write_bytes(const std::string& path, const unsigned char* data, std::size_t data_size) {
    if (path.empty() || (data == nullptr && data_size != 0)) {
        return false;
    }
    const std::filesystem::path target(path);
    if (!ensure_parent_directory(target)) {
        return false;
    }
    std::ofstream output(target, std::ios::binary | std::ios::trunc);
    if (!output) {
        return false;
    }
    if (data_size != 0) {
        output.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(data_size));
    }
    return output.good();
}

bool write_text_utf8(const std::string& path, const std::string& text) {
    return write_bytes(
        path,
        reinterpret_cast<const unsigned char*>(text.data()),
        text.size()
    );
}

bool write_text(const std::string& path, const std::string& text, const std::string& encoding) {
    if (path.empty()) {
        return false;
    }
    if (encoding.empty()) {
        return write_text_utf8(path, text);
    }
    std::string normalized;
    normalized.reserve(encoding.size());
    for (const char ch : encoding) {
        if (ch != '-') {
            normalized.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
        }
    }
    return normalized == "utf8" && write_text_utf8(path, text);
}

} // namespace ghostrigger::core::io::files::local_file_writer

extern "C" {

GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_bytes(
    const char* path,
    const unsigned char* data,
    std::size_t data_size
) {
    return ghostrigger::core::io::files::local_file_writer::write_bytes(
        path == nullptr ? std::string{} : std::string(path),
        data,
        data_size
    ) ? 1 : 0;
}

GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_text(
    const char* path,
    const char* text,
    const char* encoding
) {
    return ghostrigger::core::io::files::local_file_writer::write_text(
        path == nullptr ? std::string{} : std::string(path),
        text == nullptr ? std::string{} : std::string(text),
        encoding == nullptr ? std::string{} : std::string(encoding)
    ) ? 1 : 0;
}

GHOSTRIGGER_CORE_IO_FILES_API int gr_core_io_files_write_text_utf8(
    const char* path,
    const char* text
) {
    return ghostrigger::core::io::files::local_file_writer::write_text_utf8(
        path == nullptr ? std::string{} : std::string(path),
        text == nullptr ? std::string{} : std::string(text)
    ) ? 1 : 0;
}

}
