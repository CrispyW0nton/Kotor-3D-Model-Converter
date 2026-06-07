#pragma once

#ifndef NOMINMAX
#define NOMINMAX
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

#include <cstddef>
#include <string>

namespace ghostrigger::native_payload {

inline HMODULE module_from_symbol(const void* symbol) {
    HMODULE module = nullptr;
    if (symbol == nullptr) {
        return nullptr;
    }
    GetModuleHandleExW(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(const_cast<void*>(symbol)),
        &module
    );
    return module;
}

inline const char* manifest_json_from_module_symbol(const void* symbol) {
    static std::string empty_manifest = R"({"schema":"ghostrigger_python_payload.v1","project":"","file_count":0,"files":[]})";
    static std::string manifest;

    HMODULE module = module_from_symbol(symbol);
    if (module == nullptr) {
        return empty_manifest.c_str();
    }

    HRSRC resource = FindResourceA(module, "PYTHON_PAYLOAD_MANIFEST", MAKEINTRESOURCEA(10));
    if (resource == nullptr) {
        return empty_manifest.c_str();
    }

    HGLOBAL handle = LoadResource(module, resource);
    if (handle == nullptr) {
        return empty_manifest.c_str();
    }

    const DWORD size = SizeofResource(module, resource);
    const void* data = LockResource(handle);
    if (data == nullptr || size == 0) {
        return empty_manifest.c_str();
    }

    manifest.assign(static_cast<const char*>(data), static_cast<std::size_t>(size));
    return manifest.c_str();
}

inline unsigned int file_count_from_manifest_json(const char* manifest_json) {
    if (manifest_json == nullptr) {
        return 0;
    }

    const std::string manifest(manifest_json);
    const std::string needle = "\"file_count\"";
    const std::size_t key = manifest.find(needle);
    if (key == std::string::npos) {
        return 0;
    }

    const std::size_t colon = manifest.find(':', key + needle.size());
    if (colon == std::string::npos) {
        return 0;
    }

    std::size_t cursor = colon + 1;
    while (cursor < manifest.size() && (manifest[cursor] == ' ' || manifest[cursor] == '\t')) {
        ++cursor;
    }

    unsigned int value = 0;
    while (cursor < manifest.size() && manifest[cursor] >= '0' && manifest[cursor] <= '9') {
        value = value * 10u + static_cast<unsigned int>(manifest[cursor] - '0');
        ++cursor;
    }
    return value;
}

} // namespace ghostrigger::native_payload
