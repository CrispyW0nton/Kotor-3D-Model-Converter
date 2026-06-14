#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define PY_SSIZE_T_CLEAN
#include <windows.h>
#include <shellapi.h>

#include "GhostRiggerNativeDependencies.h"

#include <cwchar>
#include <cwctype>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#ifdef _DEBUG
#define GHOSTRIGGER_RESTORE_DEBUG_MACRO
#undef _DEBUG
#endif
#include <Python.h>
#ifdef GHOSTRIGGER_RESTORE_DEBUG_MACRO
#define _DEBUG
#undef GHOSTRIGGER_RESTORE_DEBUG_MACRO
#endif

namespace fs = std::filesystem;

namespace {

constexpr const wchar_t* kDefaultPython313 = L"C:\\Users\\KingJamesIX\\AppData\\Local\\Programs\\Python\\Python313\\python.exe";
constexpr const wchar_t* kDefaultPython313Home = L"C:\\Users\\KingJamesIX\\AppData\\Local\\Programs\\Python\\Python313";
constexpr const wchar_t* kNativeHostDebugArg = L"--native-host-debug";
constexpr const wchar_t* kNativeEmbedInitDebugArg = L"--native-embed-init-debug";

std::wstring quote(const std::wstring& value) {
    std::wstring result = L"\"";
    for (wchar_t ch : value) {
        if (ch == L'"') {
            result += L'\\';
        }
        result += ch;
    }
    result += L"\"";
    return result;
}

std::string utf8_from_wstring(const std::wstring& value) {
    if (value.empty()) {
        return {};
    }

    const int required = WideCharToMultiByte(
        CP_UTF8,
        0,
        value.c_str(),
        static_cast<int>(value.size()),
        nullptr,
        0,
        nullptr,
        nullptr
    );
    if (required <= 0) {
        return {};
    }

    std::string result(static_cast<std::size_t>(required), '\0');
    WideCharToMultiByte(
        CP_UTF8,
        0,
        value.c_str(),
        static_cast<int>(value.size()),
        result.data(),
        required,
        nullptr,
        nullptr
    );
    return result;
}

std::wstring wstring_from_utf8(const std::string& value) {
    if (value.empty()) {
        return {};
    }

    const int required = MultiByteToWideChar(
        CP_UTF8,
        0,
        value.c_str(),
        static_cast<int>(value.size()),
        nullptr,
        0
    );
    if (required <= 0) {
        return {};
    }

    std::wstring result(static_cast<std::size_t>(required), L'\0');
    MultiByteToWideChar(
        CP_UTF8,
        0,
        value.c_str(),
        static_cast<int>(value.size()),
        result.data(),
        required
    );
    return result;
}

std::string python_string_literal(const std::string& value) {
    std::string result = "'";
    for (char ch : value) {
        if (ch == '\\' || ch == '\'') {
            result.push_back('\\');
        }
        result.push_back(ch);
    }
    result.push_back('\'');
    return result;
}

std::optional<fs::path> executable_directory() {
    std::wstring buffer(MAX_PATH, L'\0');
    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0) {
        return std::nullopt;
    }

    while (length == buffer.size()) {
        buffer.resize(buffer.size() * 2, L'\0');
        length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
        if (length == 0) {
            return std::nullopt;
        }
    }

    buffer.resize(length);
    return fs::path(buffer).parent_path();
}

std::optional<fs::path> find_repo_root() {
    std::vector<fs::path> starts;
    starts.push_back(fs::current_path());

    if (auto exe_dir = executable_directory()) {
        starts.push_back(*exe_dir);
    }

    for (const fs::path& start : starts) {
        fs::path cursor = fs::weakly_canonical(start);
        for (int depth = 0; depth < 10; ++depth) {
            if (
                fs::exists(cursor / L"GhostRigger.sln") ||
                (fs::exists(cursor / L"pyproject.toml") && fs::exists(cursor / L"native"))
            ) {
                return cursor;
            }
            if (!cursor.has_parent_path() || cursor.parent_path() == cursor) {
                break;
            }
            cursor = cursor.parent_path();
        }
    }

    return std::nullopt;
}

std::wstring get_env_wstring(const wchar_t* name) {
    DWORD required = GetEnvironmentVariableW(name, nullptr, 0);
    if (required == 0) {
        return L"";
    }

    std::wstring value(required, L'\0');
    DWORD written = GetEnvironmentVariableW(name, value.data(), required);
    if (written == 0) {
        return L"";
    }

    value.resize(written);
    return value;
}

bool env_enabled(const wchar_t* name) {
    const std::wstring value = get_env_wstring(name);
    if (value.empty()) {
        return false;
    }

    std::wstring lowered;
    lowered.reserve(value.size());
    for (wchar_t ch : value) {
        lowered.push_back(static_cast<wchar_t>(towlower(ch)));
    }
    return lowered == L"1" || lowered == L"true" || lowered == L"yes" || lowered == L"on" || lowered == L"debug";
}

bool env_disabled(const wchar_t* name) {
    const std::wstring value = get_env_wstring(name);
    if (value.empty()) {
        return false;
    }

    std::wstring lowered;
    lowered.reserve(value.size());
    for (wchar_t ch : value) {
        lowered.push_back(static_cast<wchar_t>(towlower(ch)));
    }
    return lowered == L"0" || lowered == L"false" || lowered == L"no" || lowered == L"off" || lowered == L"never";
}

std::string last_win32_error_text(DWORD error_code) {
    if (error_code == 0) {
        return "";
    }
    return "win32_error_" + std::to_string(error_code);
}

using StringExport = const char* (*)();
using FileCountExport = unsigned int (*)();

void print_native_log_line(
    const char* level,
    const char* source,
    const std::string& message,
    WORD message_color = FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE
);

struct PythonPayloadRow {
    std::string resource_name;
    std::string packaged_path;
};

std::string json_string_value(const std::string& object_text, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    const std::size_t key_pos = object_text.find(needle);
    if (key_pos == std::string::npos) {
        return "";
    }
    const std::size_t colon = object_text.find(':', key_pos + needle.size());
    if (colon == std::string::npos) {
        return "";
    }
    std::size_t cursor = object_text.find('"', colon + 1);
    if (cursor == std::string::npos) {
        return "";
    }
    ++cursor;

    std::string result;
    bool escaped = false;
    for (; cursor < object_text.size(); ++cursor) {
        const char ch = object_text[cursor];
        if (escaped) {
            result.push_back(ch == '\\' ? '\\' : ch);
            escaped = false;
            continue;
        }
        if (ch == '\\') {
            escaped = true;
            continue;
        }
        if (ch == '"') {
            break;
        }
        result.push_back(ch);
    }
    return result;
}

std::vector<PythonPayloadRow> parse_payload_rows(const std::string& manifest) {
    std::vector<PythonPayloadRow> rows;
    const std::size_t files_key = manifest.find("\"files\"");
    if (files_key == std::string::npos) {
        return rows;
    }
    const std::size_t array_start = manifest.find('[', files_key);
    if (array_start == std::string::npos) {
        return rows;
    }

    std::size_t cursor = array_start + 1;
    while (cursor < manifest.size()) {
        const std::size_t object_start = manifest.find('{', cursor);
        if (object_start == std::string::npos) {
            break;
        }
        const std::size_t object_end = manifest.find('}', object_start + 1);
        if (object_end == std::string::npos) {
            break;
        }
        const std::string object_text = manifest.substr(object_start, object_end - object_start + 1);
        PythonPayloadRow row{
            json_string_value(object_text, "resource_name"),
            json_string_value(object_text, "packaged_path")
        };
        if (!row.resource_name.empty() && !row.packaged_path.empty()) {
            rows.push_back(row);
        }
        cursor = object_end + 1;
    }
    return rows;
}

std::string read_string_export(HMODULE module, const char* export_name, bool& present) {
    present = false;
    if (module == nullptr || export_name == nullptr || export_name[0] == '\0') {
        return "";
    }
    FARPROC proc = GetProcAddress(module, export_name);
    if (proc == nullptr) {
        return "";
    }
    present = true;
    const char* value = reinterpret_cast<StringExport>(proc)();
    return value == nullptr ? "" : std::string(value);
}

enum class PayloadWriteStatus {
    Failed,
    Written,
    AlreadyExists,
};

PayloadWriteStatus extract_rcdata_resource(HMODULE module, const std::string& resource_name, const fs::path& destination) {
    if (module == nullptr || resource_name.empty()) {
        return PayloadWriteStatus::Failed;
    }
    std::error_code exists_error;
    if (fs::exists(destination, exists_error)) {
        return exists_error ? PayloadWriteStatus::Failed : PayloadWriteStatus::AlreadyExists;
    }
    HRSRC resource = FindResourceA(module, resource_name.c_str(), MAKEINTRESOURCEA(10));
    if (resource == nullptr) {
        return PayloadWriteStatus::Failed;
    }
    HGLOBAL handle = LoadResource(module, resource);
    if (handle == nullptr) {
        return PayloadWriteStatus::Failed;
    }
    const DWORD size = SizeofResource(module, resource);
    const void* data = LockResource(handle);
    if (data == nullptr || size == 0) {
        return PayloadWriteStatus::Failed;
    }

    std::error_code error;
    fs::create_directories(destination.parent_path(), error);
    if (error) {
        return PayloadWriteStatus::Failed;
    }
    std::ofstream stream(destination, std::ios::binary | std::ios::trunc);
    if (!stream) {
        return PayloadWriteStatus::Failed;
    }
    stream.write(static_cast<const char*>(data), static_cast<std::streamsize>(size));
    return static_cast<bool>(stream) ? PayloadWriteStatus::Written : PayloadWriteStatus::Failed;
}

bool extract_python_payloads_to_import_root(const fs::path& output_dir, const fs::path& payload_root) {
    std::size_t dll_count = 0;
    std::size_t written_count = 0;
    std::size_t skipped_count = 0;

    for (std::size_t index = 0; index < ghostrigger::native::core::host::kNativeDependencySpecCount; ++index) {
        const auto& spec = ghostrigger::native::core::host::kNativeDependencySpecs[index];
        const fs::path dll_path = output_dir / spec.dll_name;
        HMODULE module = LoadLibraryExW(dll_path.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (module == nullptr) {
            continue;
        }

        bool manifest_present = false;
        const std::string manifest = read_string_export(module, "gr_python_payload_manifest_json", manifest_present);
        if (!manifest_present || manifest.empty()) {
            continue;
        }

        std::size_t prepared_for_dll = 0;
        for (const PythonPayloadRow& row : parse_payload_rows(manifest)) {
            std::string relative = row.packaged_path;
            for (char& ch : relative) {
                if (ch == '\\') {
                    ch = '/';
                }
            }
            constexpr const char* prefix = "Python/";
            if (relative.rfind(prefix, 0) == 0) {
                relative.erase(0, std::char_traits<char>::length(prefix));
            }
            if (relative.empty() || relative.find("..") != std::string::npos) {
                continue;
            }
            const std::wstring relative_wide = wstring_from_utf8(relative);
            if (relative_wide.empty()) {
                continue;
            }
            const PayloadWriteStatus status = extract_rcdata_resource(
                module,
                row.resource_name,
                payload_root / fs::path(relative_wide)
            );
            if (status == PayloadWriteStatus::Written) {
                ++prepared_for_dll;
                ++written_count;
            } else if (status == PayloadWriteStatus::AlreadyExists) {
                ++prepared_for_dll;
                ++skipped_count;
            }
        }
        if (prepared_for_dll > 0) {
            ++dll_count;
        }
    }

    if (dll_count == 0 || (written_count + skipped_count) == 0) {
        print_native_log_line(
            "WARN",
            "ghostrigger.native",
            "No embedded Python payload files were prepared; startup may still depend on repo src.",
            FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY
        );
        return false;
    }

    std::ostringstream message;
    message << "Prepared embedded Python payloads from " << dll_count << " DLL(s): " << written_count
        << " written, " << skipped_count << " already present, into "
        << utf8_from_wstring(payload_root.wstring());
    print_native_log_line("INFO", "ghostrigger.native", message.str(), FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    return true;
}

unsigned int read_file_count_export(HMODULE module, bool& present) {
    present = false;
    if (module == nullptr) {
        return 0;
    }
    FARPROC proc = GetProcAddress(module, "gr_python_payload_file_count");
    if (proc == nullptr) {
        return 0;
    }
    present = true;
    return reinterpret_cast<FileCountExport>(proc)();
}

WORD default_console_attributes() {
    CONSOLE_SCREEN_BUFFER_INFO info{};
    HANDLE handle = GetStdHandle(STD_OUTPUT_HANDLE);
    if (handle == INVALID_HANDLE_VALUE || !GetConsoleScreenBufferInfo(handle, &info)) {
        return FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE;
    }
    return info.wAttributes;
}

void set_console_color(WORD color) {
    HANDLE handle = GetStdHandle(STD_OUTPUT_HANDLE);
    if (handle != INVALID_HANDLE_VALUE) {
        SetConsoleTextAttribute(handle, color);
    }
}

std::string current_time_hhmmss() {
    SYSTEMTIME time{};
    GetLocalTime(&time);
    char buffer[16] = {};
    std::snprintf(buffer, sizeof(buffer), "%02u:%02u:%02u", time.wHour, time.wMinute, time.wSecond);
    return buffer;
}

const char* status_level(bool available, bool payload_ready) {
    return (available && payload_ready) ? "INFO" : "WARN";
}

WORD status_color(bool available, bool payload_ready) {
    if (available && payload_ready) {
        return FOREGROUND_GREEN | FOREGROUND_INTENSITY;
    }
    if (!available) {
        return FOREGROUND_RED | FOREGROUND_INTENSITY;
    }
    return FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY;
}

void print_native_log_line(
    const char* level,
    const char* source,
    const std::string& message,
    WORD message_color
) {
    const WORD normal = default_console_attributes();
    const std::string time = current_time_hhmmss();
    set_console_color(FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    std::printf("%s  ", time.c_str());
    set_console_color(FOREGROUND_GREEN | FOREGROUND_BLUE | FOREGROUND_INTENSITY);
    std::printf("%-5s  ", level);
    set_console_color(FOREGROUND_BLUE | FOREGROUND_INTENSITY);
    std::printf("%-24s", source);
    set_console_color(message_color);
    std::printf("%s\n", message.c_str());
    set_console_color(normal);
}

void log_native_dependency_audit_to_console(const fs::path& output_dir) {
    std::size_t available_count = 0;
    std::size_t payload_ready_count = 0;
    struct Row {
        std::wstring dll_name;
        bool available = false;
        bool payload_count_present = false;
        bool payload_ready = false;
        unsigned int file_count = 0;
        std::string reason;
    };
    std::vector<Row> rows;
    rows.reserve(ghostrigger::native::core::host::kNativeDependencySpecCount);

    for (std::size_t index = 0; index < ghostrigger::native::core::host::kNativeDependencySpecCount; ++index) {
        const auto& spec = ghostrigger::native::core::host::kNativeDependencySpecs[index];
        const fs::path dll_path = output_dir / spec.dll_name;
        Row row{};
        row.dll_name = spec.dll_name;

        HMODULE module = LoadLibraryExW(dll_path.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        const DWORD load_error = module == nullptr ? GetLastError() : 0;
        row.available = module != nullptr;
        if (row.available) {
            ++available_count;
        }

        row.file_count = read_file_count_export(module, row.payload_count_present);
        row.payload_ready = row.payload_count_present && row.file_count > 0;
        if (row.payload_ready) {
            ++payload_ready_count;
        }
        if (!row.available) {
            row.reason = last_win32_error_text(load_error);
        }
        rows.push_back(row);
    }

    const std::size_t dependency_count = ghostrigger::native::core::host::kNativeDependencySpecCount;
    print_native_log_line("INFO", "ghostrigger.native", "============================================================");
    print_native_log_line("INFO", "ghostrigger.native", "GhostRigger Native dependency audit");
    {
        std::ostringstream summary;
        summary << "DLLs loaded: " << available_count << "/" << dependency_count
            << " | Python payload manifests: " << payload_ready_count << "/" << dependency_count;
        print_native_log_line("INFO", "ghostrigger.native", summary.str());
    }
    print_native_log_line("INFO", "ghostrigger.native", "============================================================");

    for (std::size_t index = 0; index < rows.size(); ++index) {
        const Row& row = rows[index];
        const char* state = row.available && row.payload_ready ? "OK" : "CHECK";
        if (!row.available) {
            state = "MISSING";
        } else if (!row.payload_ready) {
            state = "NO_PAYLOAD";
        }
        std::ostringstream message;
        message << "Native DLL dependency " << (index + 1) << "/" << rows.size()
            << " " << state << " " << utf8_from_wstring(row.dll_name);
        print_native_log_line(status_level(row.available, row.payload_ready), "ghostrigger.native", message.str(), status_color(row.available, row.payload_ready));
    }
    print_native_log_line("INFO", "ghostrigger.native", "============================================================");
}

void open_log_console() {
    if (env_disabled(L"GHOSTRIGGER_NATIVE_LOG_CONSOLE")) {
        return;
    }

    if (!AllocConsole()) {
        return;
    }

    SetConsoleTitleW(L"Select GhostRigger");
    FILE* stream = nullptr;
    freopen_s(&stream, "CONOUT$", "w", stdout);
    freopen_s(&stream, "CONOUT$", "w", stderr);
    freopen_s(&stream, "CONIN$", "r", stdin);
    SetStdHandle(STD_OUTPUT_HANDLE, GetStdHandle(STD_OUTPUT_HANDLE));
    SetStdHandle(STD_ERROR_HANDLE, GetStdHandle(STD_ERROR_HANDLE));
    SetStdHandle(STD_INPUT_HANDLE, GetStdHandle(STD_INPUT_HANDLE));
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    std::setvbuf(stderr, nullptr, _IONBF, 0);
}

void show_error(const std::wstring& message) {
    MessageBoxW(nullptr, message.c_str(), L"GhostRigger Native Host", MB_OK | MB_ICONERROR | MB_SETFOREGROUND);
}

bool has_arg(int argc, wchar_t* argv[], const wchar_t* expected) {
    for (int index = 1; index < argc; ++index) {
        if (wcscmp(argv[index], expected) == 0) {
            return true;
        }
    }
    return false;
}

std::wstring join_args(int argc, wchar_t* argv[]) {
    std::wostringstream stream;
    bool emitted_arg = false;
    for (int index = 1; index < argc; ++index) {
        if (wcscmp(argv[index], kNativeHostDebugArg) == 0) {
            continue;
        }
        if (wcscmp(argv[index], kNativeEmbedInitDebugArg) == 0) {
            continue;
        }
        if (emitted_arg) {
            stream << L' ';
        }
        stream << quote(argv[index]);
        emitted_arg = true;
    }
    return stream.str();
}

std::optional<fs::path> python_home_from_override(const std::wstring& python_override) {
    if (python_override.empty()) {
        return std::nullopt;
    }

    fs::path path = python_override;
    if (path.has_filename()) {
        path = path.parent_path();
    }
    if (fs::exists(path / L"python313.dll") && fs::exists(path / L"Lib")) {
        return path;
    }
    return std::nullopt;
}

std::optional<fs::path> find_python_home() {
    if (auto override_home = python_home_from_override(get_env_wstring(L"GHOSTRIGGER_PYTHON"))) {
        return override_home;
    }

    const fs::path default_home = kDefaultPython313Home;
    if (fs::exists(default_home / L"python313.dll") && fs::exists(default_home / L"Lib")) {
        return default_home;
    }

    return std::nullopt;
}

bool append_python_arg(PyConfig& config, const std::wstring& arg) {
    PyStatus status = PyWideStringList_Append(&config.argv, arg.c_str());
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        show_error(L"GhostRigger.Native.Core.Host could not configure embedded Python argv.");
        return false;
    }
    return true;
}

bool set_python_config_string(PyConfig& config, wchar_t** field, const std::wstring& value) {
    PyStatus status = PyConfig_SetString(&config, field, value.c_str());
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        show_error(L"GhostRigger.Native.Core.Host could not configure embedded Python paths.");
        return false;
    }
    return true;
}

bool configure_embedded_python(PyConfig& config, const fs::path& repo_root, const fs::path& python_home, int argc, wchar_t* argv[]) {
    const fs::path main_py = executable_directory().value_or(repo_root) / L"main.py";
    const fs::path python_exe = python_home / L"python.exe";

    PyConfig_InitPythonConfig(&config);
    config.parse_argv = 0;
    config.isolated = 0;
    config.use_environment = 1;
    config.site_import = 1;
    config.install_signal_handlers = 1;

    if (!set_python_config_string(config, &config.home, python_home.wstring())) {
        return false;
    }

    auto exe_dir = executable_directory();
    const std::wstring program_name = exe_dir ? ((*exe_dir / L"GhostRigger.exe").wstring()) : L"GhostRigger.exe";
    if (!set_python_config_string(config, &config.program_name, program_name)) {
        return false;
    }
    if (fs::exists(python_exe) && !set_python_config_string(config, &config.executable, python_exe.wstring())) {
        return false;
    }

    if (!append_python_arg(config, main_py.wstring())) {
        return false;
    }
    const std::wstring forwarded_args = join_args(argc, argv);
    if (forwarded_args.empty()) {
        if (!append_python_arg(config, L"--gui") || !append_python_arg(config, L"qt")) {
            return false;
        }
    } else {
        for (int index = 1; index < argc; ++index) {
            if (
                wcscmp(argv[index], kNativeHostDebugArg) == 0 ||
                wcscmp(argv[index], kNativeEmbedInitDebugArg) == 0
            ) {
                continue;
            }
            if (!append_python_arg(config, argv[index])) {
                return false;
            }
        }
    }

    return true;
}

int initialize_embedded_python(const fs::path& repo_root, const fs::path& python_home, int argc, wchar_t* argv[]) {
    SetCurrentDirectoryW(repo_root.c_str());
    SetDllDirectoryW(python_home.c_str());
    SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_HOST", L"1");
    SetEnvironmentVariableW(L"GHOSTRIGGER_EMBEDDED_PYTHON", L"1");
    SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_REPO_ROOT", repo_root.c_str());
    const fs::path native_main_py = executable_directory().value_or(repo_root) / L"main.py";
    SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_PYTHON_ENTRYPOINT", native_main_py.c_str());
    SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_PAYLOAD_AUDIT_REQUIRED", L"1");
    if (auto exe_dir = executable_directory()) {
        SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_BUILD_OUTPUT_DIR", exe_dir->c_str());
        const fs::path payload_root = *exe_dir / L"GhostRiggerPythonPayload";
        if (extract_python_payloads_to_import_root(*exe_dir, payload_root)) {
            SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_PAYLOAD_ROOT", payload_root.c_str());
        }
    }

    PyStatus status;
    PyConfig config;
    if (!configure_embedded_python(config, repo_root, python_home, argc, argv)) {
        return 5;
    }

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        show_error(L"GhostRigger.Native.Core.Host could not initialize embedded Python.");
        return 5;
    }

    return 0;
}

int run_embedded_python(int argc, wchar_t* argv[], const fs::path& repo_root, const fs::path& python_home) {
    const int init_result = initialize_embedded_python(repo_root, python_home, argc, argv);
    if (init_result != 0) {
        return init_result;
    }
    if (has_arg(argc, argv, kNativeEmbedInitDebugArg)) {
        return Py_FinalizeEx() == 0 ? 0 : 8;
    }

    const fs::path main_py = executable_directory().value_or(repo_root) / L"main.py";
    if (!fs::exists(main_py)) {
        Py_FinalizeEx();
        show_error(L"GhostRigger.Native.Core.Host could not find its native main.py beside GhostRigger.exe.");
        return 6;
    }
    const std::string main_py_utf8 = utf8_from_wstring(main_py.wstring());
    if (main_py_utf8.empty()) {
        Py_FinalizeEx();
        show_error(L"GhostRigger.Native.Core.Host could not convert main.py path for embedded Python.");
        return 6;
    }

    const std::string run_command =
        "import runpy, sys\n"
        "try:\n"
        "    sys.stdout = open('CONOUT$', 'w', buffering=1, encoding='utf-8', errors='replace')\n"
        "    sys.stderr = open('CONOUT$', 'w', buffering=1, encoding='utf-8', errors='replace')\n"
        "except OSError:\n"
        "    pass\n"
        "runpy.run_path(" + python_string_literal(main_py_utf8) + ", run_name='__main__')\n";
    const int run_result = PyRun_SimpleStringFlags(run_command.c_str(), nullptr);
    const int finalize_result = Py_FinalizeEx();
    if (run_result != 0) {
        show_error(L"GhostRigger.Native.Core.Host embedded Python exited after a startup error. Check Logs for details.");
        return 7;
    }
    if (finalize_result != 0) {
        return 8;
    }
    return 0;
}

int run_hosted_python(int argc, wchar_t* argv[]) {
    if (has_arg(argc, argv, kNativeHostDebugArg)) {
        return 0;
    }

    auto repo_root = find_repo_root();
    if (!repo_root) {
        show_error(L"GhostRigger.Native.Core.Host could not find GhostRigger.sln or pyproject.toml/native.");
        return 2;
    }

    auto python_home = find_python_home();
    if (!python_home) {
        show_error(
            L"GhostRigger.Native.Core.Host could not find an embeddable Python 3.13 home. "
            L"Set GHOSTRIGGER_PYTHON to a Python executable inside the Python 3.13 install."
        );
        return 3;
    }

    if (!has_arg(argc, argv, kNativeEmbedInitDebugArg)) {
        open_log_console();
    }

    if (!has_arg(argc, argv, kNativeEmbedInitDebugArg)) {
        if (auto exe_dir = executable_directory()) {
            log_native_dependency_audit_to_console(*exe_dir);
        }
    }

    return run_embedded_python(argc, argv, *repo_root, *python_home);
}

} // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == nullptr) {
        show_error(L"GhostRigger.Native.Core.Host could not parse the command line.");
        return 4;
    }

    const int result = run_hosted_python(argc, argv);
    LocalFree(argv);
    return result;
}
