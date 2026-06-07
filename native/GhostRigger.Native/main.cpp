#define WIN32_LEAN_AND_MEAN
#define PY_SSIZE_T_CLEAN
#include <windows.h>
#include <shellapi.h>

#include <cwchar>
#include <cwctype>
#include <cstdio>
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
            if (fs::exists(cursor / L"main.py") && fs::exists(cursor / L"pyproject.toml")) {
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
        show_error(L"GhostRigger.Native could not configure embedded Python argv.");
        return false;
    }
    return true;
}

bool set_python_config_string(PyConfig& config, wchar_t** field, const std::wstring& value) {
    PyStatus status = PyConfig_SetString(&config, field, value.c_str());
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        show_error(L"GhostRigger.Native could not configure embedded Python paths.");
        return false;
    }
    return true;
}

bool configure_embedded_python(PyConfig& config, const fs::path& repo_root, const fs::path& python_home, int argc, wchar_t* argv[]) {
    const fs::path main_py = repo_root / L"main.py";
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

    PyStatus status;
    PyConfig config;
    if (!configure_embedded_python(config, repo_root, python_home, argc, argv)) {
        return 5;
    }

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        show_error(L"GhostRigger.Native could not initialize embedded Python.");
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

    const fs::path main_py = repo_root / L"main.py";
    const std::string main_py_utf8 = utf8_from_wstring(main_py.wstring());
    if (main_py_utf8.empty()) {
        Py_FinalizeEx();
        show_error(L"GhostRigger.Native could not convert main.py path for embedded Python.");
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
        show_error(L"GhostRigger.Native embedded Python exited after a startup error. Check Logs for details.");
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
        show_error(L"GhostRigger.Native could not find main.py and pyproject.toml.");
        return 2;
    }

    auto python_home = find_python_home();
    if (!python_home) {
        show_error(
            L"GhostRigger.Native could not find an embeddable Python 3.13 home. "
            L"Set GHOSTRIGGER_PYTHON to a Python executable inside the Python 3.13 install."
        );
        return 3;
    }

    if (!has_arg(argc, argv, kNativeEmbedInitDebugArg)) {
        open_log_console();
    }

    return run_embedded_python(argc, argv, *repo_root, *python_home);
}

} // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == nullptr) {
        show_error(L"GhostRigger.Native could not parse the command line.");
        return 4;
    }

    const int result = run_hosted_python(argc, argv);
    LocalFree(argv);
    return result;
}
