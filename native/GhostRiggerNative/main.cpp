#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <filesystem>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

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

struct ProcessResult {
    bool started = false;
    DWORD code = 0;
};

ProcessResult run_process(const std::wstring& command, const fs::path& working_directory) {
    STARTUPINFOW startup_info{};
    startup_info.cb = sizeof(startup_info);

    PROCESS_INFORMATION process_info{};
    std::wstring mutable_command = command;

    BOOL created = CreateProcessW(
        nullptr,
        mutable_command.data(),
        nullptr,
        nullptr,
        FALSE,
        0,
        nullptr,
        working_directory.c_str(),
        &startup_info,
        &process_info
    );

    if (!created) {
        return ProcessResult{false, GetLastError()};
    }

    WaitForSingleObject(process_info.hProcess, INFINITE);

    DWORD exit_code = 0;
    GetExitCodeProcess(process_info.hProcess, &exit_code);
    CloseHandle(process_info.hThread);
    CloseHandle(process_info.hProcess);
    return ProcessResult{true, exit_code};
}

std::wstring join_args(int argc, wchar_t* argv[]) {
    std::wostringstream stream;
    for (int index = 1; index < argc; ++index) {
        if (index > 1) {
            stream << L' ';
        }
        stream << quote(argv[index]);
    }
    return stream.str();
}

} // namespace

int wmain(int argc, wchar_t* argv[]) {
    auto repo_root = find_repo_root();
    if (!repo_root) {
        std::wcerr << L"GhostRiggerNative could not find main.py and pyproject.toml." << std::endl;
        return 2;
    }

    const fs::path main_py = *repo_root / L"main.py";
    const std::wstring python_override = get_env_wstring(L"GHOSTRIGGER_PYTHON");

    std::vector<std::wstring> python_commands;
    if (!python_override.empty()) {
        python_commands.push_back(python_override);
    }
    python_commands.push_back(L"py -3");
    python_commands.push_back(L"python");

    const std::wstring forwarded_args = join_args(argc, argv);
    const std::wstring app_args = forwarded_args.empty() ? L"--gui qt" : forwarded_args;

    for (const std::wstring& python_command : python_commands) {
        const std::wstring command = python_command + L" " + quote(main_py.wstring()) + L" " + app_args;
        const ProcessResult result = run_process(command, *repo_root);
        if (result.started) {
            return static_cast<int>(result.code);
        }
        if (result.code != ERROR_FILE_NOT_FOUND && result.code != ERROR_PATH_NOT_FOUND) {
            std::wcerr << L"GhostRiggerNative failed to start Python. Windows error: " << result.code << std::endl;
            return static_cast<int>(result.code);
        }
    }

    std::wcerr
        << L"GhostRiggerNative could not start Python. Install Python 3, use the py launcher, "
        << L"or set GHOSTRIGGER_PYTHON to a Python executable path."
        << std::endl;
    return 3;
}
