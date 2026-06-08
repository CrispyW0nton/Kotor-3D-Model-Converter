#include "LocalFileWriter.h"

#include <filesystem>
#include <fstream>

namespace ghostrigger::adapters::files::local_file_writer {
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

} // namespace ghostrigger::adapters::files::local_file_writer

extern "C" {

GHOSTRIGGER_ADAPTERS_FILES_API int gr_adapters_files_write_bytes(
    const char* path,
    const unsigned char* data,
    std::size_t data_size
) {
    return ghostrigger::adapters::files::local_file_writer::write_bytes(
        path == nullptr ? std::string{} : std::string(path),
        data,
        data_size
    ) ? 1 : 0;
}

GHOSTRIGGER_ADAPTERS_FILES_API int gr_adapters_files_write_text_utf8(
    const char* path,
    const char* text
) {
    return ghostrigger::adapters::files::local_file_writer::write_text_utf8(
        path == nullptr ? std::string{} : std::string(path),
        text == nullptr ? std::string{} : std::string(text)
    ) ? 1 : 0;
}

}
