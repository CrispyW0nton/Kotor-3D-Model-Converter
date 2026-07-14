#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <dinput.h>

#include <algorithm>
#include <cctype>
#include <cwctype>
#include <deque>
#include <fstream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr GUID kGuidSysMouse = {
    0x6F1D2B60, 0xD5A0, 0x11CF, {0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00}
};
constexpr GUID kGuidSysKeyboard = {
    0x6F1D2B61, 0xD5A0, 0x11CF, {0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00}
};

enum class DeviceKind {
    Unknown,
    Mouse,
    Keyboard,
};

struct InjectedEvent {
    DeviceKind kind = DeviceKind::Unknown;
    DWORD offset = 0;
    DWORD data = 0;
};

HMODULE g_realDInput = nullptr;
std::wstring g_commandPath;
std::wstring g_logPath;
std::wstring g_hostExe;
std::mutex g_mutex;
std::deque<InjectedEvent> g_events;
int g_mouseLeftPolls = 0;
int g_keyPolls[256] = {};
DWORD g_sequence = 1;

using DirectInput8CreateFn = HRESULT(WINAPI *)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);
using DllCanUnloadNowFn = HRESULT(WINAPI *)();
using DllGetClassObjectFn = HRESULT(WINAPI *)(REFCLSID, REFIID, LPVOID *);
using DllRegisterServerFn = HRESULT(WINAPI *)();
using DllUnregisterServerFn = HRESULT(WINAPI *)();
using GetdfDIJoystickFn = LPCDIDATAFORMAT(WINAPI *)();

std::wstring directoryOf(HMODULE module) {
    wchar_t buffer[MAX_PATH] = {};
    GetModuleFileNameW(module, buffer, MAX_PATH);
    std::wstring path(buffer);
    const size_t slash = path.find_last_of(L"\\/");
    if (slash == std::wstring::npos) {
        return L".";
    }
    return path.substr(0, slash);
}

std::wstring fileNameOf(const std::wstring &path) {
    const size_t slash = path.find_last_of(L"\\/");
    if (slash == std::wstring::npos) {
        return path;
    }
    return path.substr(slash + 1);
}

std::wstring currentProcessPath() {
    wchar_t buffer[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, buffer, MAX_PATH);
    return std::wstring(buffer);
}

std::string utf8(const std::wstring &value) {
    if (value.empty()) {
        return {};
    }
    int size = WideCharToMultiByte(CP_UTF8, 0, value.c_str(), -1, nullptr, 0, nullptr, nullptr);
    if (size <= 1) {
        return {};
    }
    std::string out(static_cast<size_t>(size - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.c_str(), -1, out.data(), size, nullptr, nullptr);
    return out;
}

void appendLog(const std::string &line) {
    if (g_logPath.empty()) {
        return;
    }
    std::ofstream out(g_logPath, std::ios::app);
    out << line << "\n";
}

HMODULE realDInput() {
    if (g_realDInput) {
        return g_realDInput;
    }
    wchar_t systemDir[MAX_PATH] = {};
    GetSystemDirectoryW(systemDir, MAX_PATH);
    std::wstring path(systemDir);
    path += L"\\dinput8.dll";
    g_realDInput = LoadLibraryW(path.c_str());
    return g_realDInput;
}

std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return value;
}

int parseInt(const std::string &text, int fallback) {
    if (text.empty()) {
        return fallback;
    }
    try {
        size_t used = 0;
        int base = 10;
        if (text.size() > 2 && text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
            base = 16;
        }
        int value = std::stoi(text, &used, base);
        return used == text.size() ? value : fallback;
    } catch (...) {
        return fallback;
    }
}

void pushEvent(DeviceKind kind, DWORD offset, DWORD data) {
    g_events.push_back(InjectedEvent{kind, offset, data});
}

void holdKey(int key, int polls) {
    if (key >= 0 && key < 256) {
        g_keyPolls[key] = std::max(g_keyPolls[key], polls);
    }
}

void pushKeyTap(int key) {
    if (key >= 0 && key < 256) {
        pushEvent(DeviceKind::Keyboard, static_cast<DWORD>(key), 0x80);
        pushEvent(DeviceKind::Keyboard, static_cast<DWORD>(key), 0x00);
    }
}

void parseCommandLine(const std::string &line) {
    std::istringstream input(line);
    std::string command;
    input >> command;
    command = lower(command);
    if (command.empty() || command[0] == '#') {
        return;
    }
    if (command == "mouse_click") {
        std::string pollsText;
        input >> pollsText;
        g_mouseLeftPolls = std::max(g_mouseLeftPolls, parseInt(pollsText, 24));
        pushEvent(DeviceKind::Mouse, DIMOFS_BUTTON0, 0x80);
        pushEvent(DeviceKind::Mouse, DIMOFS_BUTTON0, 0x00);
        appendLog("queued mouse_click");
        return;
    }
    if (command == "key_tap") {
        std::string keyText;
        std::string pollsText;
        input >> keyText >> pollsText;
        int key = parseInt(keyText, -1);
        if (key >= 0 && key < 256) {
            holdKey(key, parseInt(pollsText, 12));
            pushKeyTap(key);
            appendLog("queued key_tap");
        }
        return;
    }
    if (command == "key_combo") {
        std::string modifierText;
        std::string keyText;
        std::string pollsText;
        input >> modifierText >> keyText >> pollsText;
        int modifier = parseInt(modifierText, -1);
        int key = parseInt(keyText, -1);
        int polls = parseInt(pollsText, 12);
        if (modifier >= 0 && modifier < 256 && key >= 0 && key < 256) {
            holdKey(modifier, polls);
            holdKey(key, polls);
            pushEvent(DeviceKind::Keyboard, static_cast<DWORD>(modifier), 0x80);
            pushKeyTap(key);
            pushEvent(DeviceKind::Keyboard, static_cast<DWORD>(modifier), 0x00);
            appendLog("queued key_combo");
        }
        return;
    }
    if (command == "reset") {
        g_mouseLeftPolls = 0;
        std::fill(std::begin(g_keyPolls), std::end(g_keyPolls), 0);
        g_events.clear();
        appendLog("reset");
    }
}

void loadCommands() {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_commandPath.empty() || GetFileAttributesW(g_commandPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
        return;
    }
    std::ifstream in(g_commandPath);
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(in, line)) {
        lines.push_back(line);
    }
    in.close();
    DeleteFileW(g_commandPath.c_str());
    for (const std::string &item : lines) {
        parseCommandLine(item);
    }
}

void applyKeyboardState(DWORD cbData, LPVOID data) {
    if (cbData < 256 || !data) {
        return;
    }
    auto *keys = static_cast<unsigned char *>(data);
    std::lock_guard<std::mutex> lock(g_mutex);
    for (int i = 0; i < 256; ++i) {
        if (g_keyPolls[i] > 0) {
            keys[i] |= 0x80;
            --g_keyPolls[i];
        }
    }
}

void applyMouseState(DWORD cbData, LPVOID data) {
    if (cbData < sizeof(DIMOUSESTATE) || !data) {
        return;
    }
    auto *mouse = static_cast<DIMOUSESTATE *>(data);
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_mouseLeftPolls > 0) {
        mouse->rgbButtons[0] |= 0x80;
        --g_mouseLeftPolls;
    }
}

void appendInjectedData(DeviceKind kind, DWORD cbObjectData, LPDIDEVICEOBJECTDATA data, LPDWORD count) {
    if (!count || !data || cbObjectData < sizeof(DIDEVICEOBJECTDATA)) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    DWORD requested = *count;
    DWORD used = *count;
    while (used < requested && !g_events.empty()) {
        auto it = std::find_if(g_events.begin(), g_events.end(), [kind](const InjectedEvent &event) {
            return event.kind == kind;
        });
        if (it == g_events.end()) {
            break;
        }
        DIDEVICEOBJECTDATA *slot = reinterpret_cast<DIDEVICEOBJECTDATA *>(
            reinterpret_cast<unsigned char *>(data) + (used * cbObjectData)
        );
        slot->dwOfs = it->offset;
        slot->dwData = it->data;
        slot->dwTimeStamp = GetTickCount();
        slot->dwSequence = g_sequence++;
        slot->uAppData = 0;
        g_events.erase(it);
        ++used;
    }
    *count = used;
}

class ProxyDeviceA final : public IDirectInputDevice8A {
public:
    ProxyDeviceA(IDirectInputDevice8A *real, DeviceKind kind) : real_(real), kind_(kind) {}

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, LPVOID *out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IDirectInputDevice8A)) {
            *out = static_cast<IDirectInputDevice8A *>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs_); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG refs = InterlockedDecrement(&refs_);
        if (!refs) {
            real_->Release();
            delete this;
        }
        return refs;
    }
    HRESULT STDMETHODCALLTYPE GetCapabilities(LPDIDEVCAPS value) override { return real_->GetCapabilities(value); }
    HRESULT STDMETHODCALLTYPE EnumObjects(LPDIENUMDEVICEOBJECTSCALLBACKA cb, LPVOID ref, DWORD flags) override { return real_->EnumObjects(cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE GetProperty(REFGUID prop, LPDIPROPHEADER header) override { return real_->GetProperty(prop, header); }
    HRESULT STDMETHODCALLTYPE SetProperty(REFGUID prop, LPCDIPROPHEADER header) override { return real_->SetProperty(prop, header); }
    HRESULT STDMETHODCALLTYPE Acquire() override { return real_->Acquire(); }
    HRESULT STDMETHODCALLTYPE Unacquire() override { return real_->Unacquire(); }
    HRESULT STDMETHODCALLTYPE GetDeviceState(DWORD cbData, LPVOID data) override {
        loadCommands();
        HRESULT hr = real_->GetDeviceState(cbData, data);
        if (SUCCEEDED(hr)) {
            if (kind_ == DeviceKind::Keyboard) {
                applyKeyboardState(cbData, data);
            } else if (kind_ == DeviceKind::Mouse) {
                applyMouseState(cbData, data);
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE GetDeviceData(DWORD cbObjectData, LPDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override {
        loadCommands();
        DWORD requested = count ? *count : 0;
        HRESULT hr = real_->GetDeviceData(cbObjectData, data, count, flags);
        if (count && data && SUCCEEDED(hr)) {
            DWORD realCount = *count;
            *count = realCount;
            if (realCount < requested) {
                DWORD total = requested;
                *count = realCount;
                appendInjectedData(kind_, cbObjectData, data, &total);
                *count = total;
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE SetDataFormat(LPCDIDATAFORMAT format) override { return real_->SetDataFormat(format); }
    HRESULT STDMETHODCALLTYPE SetEventNotification(HANDLE event) override { return real_->SetEventNotification(event); }
    HRESULT STDMETHODCALLTYPE SetCooperativeLevel(HWND hwnd, DWORD flags) override { return real_->SetCooperativeLevel(hwnd, flags); }
    HRESULT STDMETHODCALLTYPE GetObjectInfo(LPDIDEVICEOBJECTINSTANCEA out, DWORD object, DWORD how) override { return real_->GetObjectInfo(out, object, how); }
    HRESULT STDMETHODCALLTYPE GetDeviceInfo(LPDIDEVICEINSTANCEA out) override { return real_->GetDeviceInfo(out); }
    HRESULT STDMETHODCALLTYPE RunControlPanel(HWND owner, DWORD flags) override { return real_->RunControlPanel(owner, flags); }
    HRESULT STDMETHODCALLTYPE Initialize(HINSTANCE inst, DWORD version, REFGUID guid) override { return real_->Initialize(inst, version, guid); }
    HRESULT STDMETHODCALLTYPE CreateEffect(REFGUID guid, LPCDIEFFECT effect, LPDIRECTINPUTEFFECT *out, LPUNKNOWN outer) override { return real_->CreateEffect(guid, effect, out, outer); }
    HRESULT STDMETHODCALLTYPE EnumEffects(LPDIENUMEFFECTSCALLBACKA cb, LPVOID ref, DWORD type) override { return real_->EnumEffects(cb, ref, type); }
    HRESULT STDMETHODCALLTYPE GetEffectInfo(LPDIEFFECTINFOA out, REFGUID guid) override { return real_->GetEffectInfo(out, guid); }
    HRESULT STDMETHODCALLTYPE GetForceFeedbackState(LPDWORD out) override { return real_->GetForceFeedbackState(out); }
    HRESULT STDMETHODCALLTYPE SendForceFeedbackCommand(DWORD flags) override { return real_->SendForceFeedbackCommand(flags); }
    HRESULT STDMETHODCALLTYPE EnumCreatedEffectObjects(LPDIENUMCREATEDEFFECTOBJECTSCALLBACK cb, LPVOID ref, DWORD flags) override { return real_->EnumCreatedEffectObjects(cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE Escape(LPDIEFFESCAPE escape) override { return real_->Escape(escape); }
    HRESULT STDMETHODCALLTYPE Poll() override { return real_->Poll(); }
    HRESULT STDMETHODCALLTYPE SendDeviceData(DWORD cbObjectData, LPCDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override { return real_->SendDeviceData(cbObjectData, data, count, flags); }
    HRESULT STDMETHODCALLTYPE EnumEffectsInFile(LPCSTR file, LPDIENUMEFFECTSINFILECALLBACK cb, LPVOID ref, DWORD flags) override { return real_->EnumEffectsInFile(file, cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE WriteEffectToFile(LPCSTR file, DWORD count, LPDIFILEEFFECT effects, DWORD flags) override { return real_->WriteEffectToFile(file, count, effects, flags); }
    HRESULT STDMETHODCALLTYPE BuildActionMap(LPDIACTIONFORMATA format, LPCSTR user, DWORD flags) override { return real_->BuildActionMap(format, user, flags); }
    HRESULT STDMETHODCALLTYPE SetActionMap(LPDIACTIONFORMATA format, LPCSTR user, DWORD flags) override { return real_->SetActionMap(format, user, flags); }
    HRESULT STDMETHODCALLTYPE GetImageInfo(LPDIDEVICEIMAGEINFOHEADERA header) override { return real_->GetImageInfo(header); }

private:
    IDirectInputDevice8A *real_ = nullptr;
    DeviceKind kind_ = DeviceKind::Unknown;
    volatile LONG refs_ = 1;
};

class ProxyDeviceW final : public IDirectInputDevice8W {
public:
    ProxyDeviceW(IDirectInputDevice8W *real, DeviceKind kind) : real_(real), kind_(kind) {}

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, LPVOID *out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IDirectInputDevice8W)) {
            *out = static_cast<IDirectInputDevice8W *>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs_); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG refs = InterlockedDecrement(&refs_);
        if (!refs) {
            real_->Release();
            delete this;
        }
        return refs;
    }
    HRESULT STDMETHODCALLTYPE GetCapabilities(LPDIDEVCAPS value) override { return real_->GetCapabilities(value); }
    HRESULT STDMETHODCALLTYPE EnumObjects(LPDIENUMDEVICEOBJECTSCALLBACKW cb, LPVOID ref, DWORD flags) override { return real_->EnumObjects(cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE GetProperty(REFGUID prop, LPDIPROPHEADER header) override { return real_->GetProperty(prop, header); }
    HRESULT STDMETHODCALLTYPE SetProperty(REFGUID prop, LPCDIPROPHEADER header) override { return real_->SetProperty(prop, header); }
    HRESULT STDMETHODCALLTYPE Acquire() override { return real_->Acquire(); }
    HRESULT STDMETHODCALLTYPE Unacquire() override { return real_->Unacquire(); }
    HRESULT STDMETHODCALLTYPE GetDeviceState(DWORD cbData, LPVOID data) override {
        loadCommands();
        HRESULT hr = real_->GetDeviceState(cbData, data);
        if (SUCCEEDED(hr)) {
            if (kind_ == DeviceKind::Keyboard) {
                applyKeyboardState(cbData, data);
            } else if (kind_ == DeviceKind::Mouse) {
                applyMouseState(cbData, data);
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE GetDeviceData(DWORD cbObjectData, LPDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override {
        loadCommands();
        DWORD requested = count ? *count : 0;
        HRESULT hr = real_->GetDeviceData(cbObjectData, data, count, flags);
        if (count && data && SUCCEEDED(hr)) {
            DWORD realCount = *count;
            *count = realCount;
            if (realCount < requested) {
                DWORD total = requested;
                *count = realCount;
                appendInjectedData(kind_, cbObjectData, data, &total);
                *count = total;
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE SetDataFormat(LPCDIDATAFORMAT format) override { return real_->SetDataFormat(format); }
    HRESULT STDMETHODCALLTYPE SetEventNotification(HANDLE event) override { return real_->SetEventNotification(event); }
    HRESULT STDMETHODCALLTYPE SetCooperativeLevel(HWND hwnd, DWORD flags) override { return real_->SetCooperativeLevel(hwnd, flags); }
    HRESULT STDMETHODCALLTYPE GetObjectInfo(LPDIDEVICEOBJECTINSTANCEW out, DWORD object, DWORD how) override { return real_->GetObjectInfo(out, object, how); }
    HRESULT STDMETHODCALLTYPE GetDeviceInfo(LPDIDEVICEINSTANCEW out) override { return real_->GetDeviceInfo(out); }
    HRESULT STDMETHODCALLTYPE RunControlPanel(HWND owner, DWORD flags) override { return real_->RunControlPanel(owner, flags); }
    HRESULT STDMETHODCALLTYPE Initialize(HINSTANCE inst, DWORD version, REFGUID guid) override { return real_->Initialize(inst, version, guid); }
    HRESULT STDMETHODCALLTYPE CreateEffect(REFGUID guid, LPCDIEFFECT effect, LPDIRECTINPUTEFFECT *out, LPUNKNOWN outer) override { return real_->CreateEffect(guid, effect, out, outer); }
    HRESULT STDMETHODCALLTYPE EnumEffects(LPDIENUMEFFECTSCALLBACKW cb, LPVOID ref, DWORD type) override { return real_->EnumEffects(cb, ref, type); }
    HRESULT STDMETHODCALLTYPE GetEffectInfo(LPDIEFFECTINFOW out, REFGUID guid) override { return real_->GetEffectInfo(out, guid); }
    HRESULT STDMETHODCALLTYPE SendForceFeedbackCommand(DWORD flags) override { return real_->SendForceFeedbackCommand(flags); }
    HRESULT STDMETHODCALLTYPE GetForceFeedbackState(LPDWORD out) override { return real_->GetForceFeedbackState(out); }
    HRESULT STDMETHODCALLTYPE EnumCreatedEffectObjects(LPDIENUMCREATEDEFFECTOBJECTSCALLBACK cb, LPVOID ref, DWORD flags) override { return real_->EnumCreatedEffectObjects(cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE Escape(LPDIEFFESCAPE escape) override { return real_->Escape(escape); }
    HRESULT STDMETHODCALLTYPE Poll() override { return real_->Poll(); }
    HRESULT STDMETHODCALLTYPE SendDeviceData(DWORD cbObjectData, LPCDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override { return real_->SendDeviceData(cbObjectData, data, count, flags); }
    HRESULT STDMETHODCALLTYPE EnumEffectsInFile(LPCWSTR file, LPDIENUMEFFECTSINFILECALLBACK cb, LPVOID ref, DWORD flags) override { return real_->EnumEffectsInFile(file, cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE WriteEffectToFile(LPCWSTR file, DWORD count, LPDIFILEEFFECT effects, DWORD flags) override { return real_->WriteEffectToFile(file, count, effects, flags); }
    HRESULT STDMETHODCALLTYPE BuildActionMap(LPDIACTIONFORMATW format, LPCWSTR user, DWORD flags) override { return real_->BuildActionMap(format, user, flags); }
    HRESULT STDMETHODCALLTYPE SetActionMap(LPDIACTIONFORMATW format, LPCWSTR user, DWORD flags) override { return real_->SetActionMap(format, user, flags); }
    HRESULT STDMETHODCALLTYPE GetImageInfo(LPDIDEVICEIMAGEINFOHEADERW header) override { return real_->GetImageInfo(header); }

private:
    IDirectInputDevice8W *real_ = nullptr;
    DeviceKind kind_ = DeviceKind::Unknown;
    volatile LONG refs_ = 1;
};

class ProxyDirectInput8A final : public IDirectInput8A {
public:
    explicit ProxyDirectInput8A(IDirectInput8A *real) : real_(real) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, LPVOID *out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IDirectInput8A)) {
            *out = static_cast<IDirectInput8A *>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs_); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG refs = InterlockedDecrement(&refs_);
        if (!refs) {
            real_->Release();
            delete this;
        }
        return refs;
    }
    HRESULT STDMETHODCALLTYPE CreateDevice(REFGUID guid, LPDIRECTINPUTDEVICE8A *out, LPUNKNOWN outer) override {
        HRESULT hr = real_->CreateDevice(guid, out, outer);
        if (SUCCEEDED(hr) && out && *out) {
            DeviceKind kind = DeviceKind::Unknown;
            if (IsEqualGUID(guid, kGuidSysMouse)) {
                kind = DeviceKind::Mouse;
            } else if (IsEqualGUID(guid, kGuidSysKeyboard)) {
                kind = DeviceKind::Keyboard;
            }
            if (kind != DeviceKind::Unknown) {
                appendLog(kind == DeviceKind::Mouse ? "wrapped mouse" : "wrapped keyboard");
                *out = new ProxyDeviceA(*out, kind);
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE EnumDevices(DWORD type, LPDIENUMDEVICESCALLBACKA cb, LPVOID ref, DWORD flags) override { return real_->EnumDevices(type, cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE GetDeviceStatus(REFGUID guid) override { return real_->GetDeviceStatus(guid); }
    HRESULT STDMETHODCALLTYPE RunControlPanel(HWND owner, DWORD flags) override { return real_->RunControlPanel(owner, flags); }
    HRESULT STDMETHODCALLTYPE Initialize(HINSTANCE inst, DWORD version) override { return real_->Initialize(inst, version); }
    HRESULT STDMETHODCALLTYPE FindDevice(REFGUID guid, LPCSTR name, LPGUID out) override { return real_->FindDevice(guid, name, out); }
    HRESULT STDMETHODCALLTYPE EnumDevicesBySemantics(LPCSTR user, LPDIACTIONFORMATA format, LPDIENUMDEVICESBYSEMANTICSCBA cb, LPVOID ref, DWORD flags) override {
        return real_->EnumDevicesBySemantics(user, format, cb, ref, flags);
    }
    HRESULT STDMETHODCALLTYPE ConfigureDevices(LPDICONFIGUREDEVICESCALLBACK cb, LPDICONFIGUREDEVICESPARAMSA params, DWORD flags, LPVOID ref) override {
        return real_->ConfigureDevices(cb, params, flags, ref);
    }

private:
    IDirectInput8A *real_ = nullptr;
    volatile LONG refs_ = 1;
};

class ProxyDirectInput8W final : public IDirectInput8W {
public:
    explicit ProxyDirectInput8W(IDirectInput8W *real) : real_(real) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, LPVOID *out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IDirectInput8W)) {
            *out = static_cast<IDirectInput8W *>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs_); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG refs = InterlockedDecrement(&refs_);
        if (!refs) {
            real_->Release();
            delete this;
        }
        return refs;
    }
    HRESULT STDMETHODCALLTYPE CreateDevice(REFGUID guid, LPDIRECTINPUTDEVICE8W *out, LPUNKNOWN outer) override {
        HRESULT hr = real_->CreateDevice(guid, out, outer);
        if (SUCCEEDED(hr) && out && *out) {
            DeviceKind kind = DeviceKind::Unknown;
            if (IsEqualGUID(guid, kGuidSysMouse)) {
                kind = DeviceKind::Mouse;
            } else if (IsEqualGUID(guid, kGuidSysKeyboard)) {
                kind = DeviceKind::Keyboard;
            }
            if (kind != DeviceKind::Unknown) {
                appendLog(kind == DeviceKind::Mouse ? "wrapped mouse W" : "wrapped keyboard W");
                *out = new ProxyDeviceW(*out, kind);
            }
        }
        return hr;
    }
    HRESULT STDMETHODCALLTYPE EnumDevices(DWORD type, LPDIENUMDEVICESCALLBACKW cb, LPVOID ref, DWORD flags) override { return real_->EnumDevices(type, cb, ref, flags); }
    HRESULT STDMETHODCALLTYPE GetDeviceStatus(REFGUID guid) override { return real_->GetDeviceStatus(guid); }
    HRESULT STDMETHODCALLTYPE RunControlPanel(HWND owner, DWORD flags) override { return real_->RunControlPanel(owner, flags); }
    HRESULT STDMETHODCALLTYPE Initialize(HINSTANCE inst, DWORD version) override { return real_->Initialize(inst, version); }
    HRESULT STDMETHODCALLTYPE FindDevice(REFGUID guid, LPCWSTR name, LPGUID out) override { return real_->FindDevice(guid, name, out); }
    HRESULT STDMETHODCALLTYPE EnumDevicesBySemantics(LPCWSTR user, LPDIACTIONFORMATW format, LPDIENUMDEVICESBYSEMANTICSCBW cb, LPVOID ref, DWORD flags) override {
        return real_->EnumDevicesBySemantics(user, format, cb, ref, flags);
    }
    HRESULT STDMETHODCALLTYPE ConfigureDevices(LPDICONFIGUREDEVICESCALLBACK cb, LPDICONFIGUREDEVICESPARAMSW params, DWORD flags, LPVOID ref) override {
        return real_->ConfigureDevices(cb, params, flags, ref);
    }

private:
    IDirectInput8W *real_ = nullptr;
    volatile LONG refs_ = 1;
};

template <typename Fn>
Fn realProc(const char *name) {
    HMODULE module = realDInput();
    if (!module) {
        return nullptr;
    }
    return reinterpret_cast<Fn>(GetProcAddress(module, name));
}

}  // namespace

extern "C" HRESULT WINAPI DirectInput8Create(HINSTANCE inst, DWORD version, REFIID riid, LPVOID *out, LPUNKNOWN outer) {
    auto fn = realProc<DirectInput8CreateFn>("DirectInput8Create");
    if (!fn) {
        return E_FAIL;
    }
    appendLog("DirectInput8Create called");
    HRESULT hr = fn(inst, version, riid, out, outer);
    if (SUCCEEDED(hr) && out && *out && IsEqualIID(riid, IID_IDirectInput8A)) {
        appendLog("wrapped IDirectInput8A");
        *out = new ProxyDirectInput8A(static_cast<IDirectInput8A *>(*out));
    } else if (SUCCEEDED(hr) && out && *out && IsEqualIID(riid, IID_IDirectInput8W)) {
        appendLog("wrapped IDirectInput8W");
        *out = new ProxyDirectInput8W(static_cast<IDirectInput8W *>(*out));
    }
    return hr;
}

extern "C" HRESULT WINAPI DllCanUnloadNow() {
    auto fn = realProc<DllCanUnloadNowFn>("DllCanUnloadNow");
    return fn ? fn() : S_FALSE;
}

extern "C" HRESULT WINAPI DllGetClassObject(REFCLSID clsid, REFIID riid, LPVOID *out) {
    auto fn = realProc<DllGetClassObjectFn>("DllGetClassObject");
    return fn ? fn(clsid, riid, out) : CLASS_E_CLASSNOTAVAILABLE;
}

extern "C" HRESULT WINAPI DllRegisterServer() {
    auto fn = realProc<DllRegisterServerFn>("DllRegisterServer");
    return fn ? fn() : E_FAIL;
}

extern "C" HRESULT WINAPI DllUnregisterServer() {
    auto fn = realProc<DllUnregisterServerFn>("DllUnregisterServer");
    return fn ? fn() : E_FAIL;
}

extern "C" LPCDIDATAFORMAT WINAPI GetdfDIJoystick() {
    auto fn = realProc<GetdfDIJoystickFn>("GetdfDIJoystick");
    return fn ? fn() : nullptr;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        std::wstring dir = directoryOf(module);
        g_commandPath = dir + L"\\kotor_dinput_proxy_commands.txt";
        g_logPath = dir + L"\\kotor_dinput_proxy.log";
        g_hostExe = fileNameOf(currentProcessPath());
        appendLog("loaded kotor dinput proxy for " + utf8(g_hostExe));
    }
    return TRUE;
}
