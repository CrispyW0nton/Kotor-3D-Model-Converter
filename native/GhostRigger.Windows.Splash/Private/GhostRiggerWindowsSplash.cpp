#include "Resource.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <objbase.h>
#include <objidl.h>
#include <propidl.h>
#include <gdiplus.h>
#include <shellapi.h>

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

#pragma comment(lib, "gdiplus.lib")

namespace
{
constexpr wchar_t kWindowClassName[] = L"GhostRiggerWindowsSplashWindow";
constexpr UINT_PTR kFrameTimerId = 1;
constexpr UINT_PTR kAutoCloseTimerId = 2;
constexpr UINT kFrameTimerMs = 16;

struct SplashState
{
    ULONG_PTR gdiplusToken = 0;
    std::unique_ptr<Gdiplus::Bitmap> logo;
    ULONGLONG startTick = 0;
    UINT autoCloseMs = 0;
    double progress = 0.0;
    std::vector<std::wstring> logLines;
};

UINT parseAutoCloseMs()
{
    int argc = 0;
    PWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    UINT value = 0;
    for (int i = 1; argv != nullptr && i < argc; ++i) {
        const std::wstring arg(argv[i]);
        constexpr wchar_t prefix[] = L"--auto-close-ms=";
        if (arg.rfind(prefix, 0) == 0) {
            value = static_cast<UINT>(std::clamp(_wtoi(arg.c_str() + (std::size(prefix) - 1)), 0, 60000));
        }
    }
    if (argv != nullptr) {
        LocalFree(argv);
    }
    return value;
}

Gdiplus::Color argb(const BYTE a, const BYTE r, const BYTE g, const BYTE b)
{
    return Gdiplus::Color(a, r, g, b);
}

Gdiplus::RectF rectf(const RECT& rect)
{
    return Gdiplus::RectF(
        static_cast<Gdiplus::REAL>(rect.left),
        static_cast<Gdiplus::REAL>(rect.top),
        static_cast<Gdiplus::REAL>(rect.right - rect.left),
        static_cast<Gdiplus::REAL>(rect.bottom - rect.top));
}

std::unique_ptr<Gdiplus::Bitmap> loadPngResource(const int resourceId)
{
    HRSRC resource = FindResourceW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(resourceId), RT_RCDATA);
    if (resource == nullptr) {
        return nullptr;
    }
    const DWORD size = SizeofResource(GetModuleHandleW(nullptr), resource);
    HGLOBAL loaded = LoadResource(GetModuleHandleW(nullptr), resource);
    const void* data = loaded != nullptr ? LockResource(loaded) : nullptr;
    if (data == nullptr || size == 0) {
        return nullptr;
    }
    HGLOBAL copy = GlobalAlloc(GMEM_MOVEABLE, size);
    if (copy == nullptr) {
        return nullptr;
    }
    void* target = GlobalLock(copy);
    if (target == nullptr) {
        GlobalFree(copy);
        return nullptr;
    }
    CopyMemory(target, data, size);
    GlobalUnlock(copy);

    IStream* stream = nullptr;
    if (CreateStreamOnHGlobal(copy, TRUE, &stream) != S_OK || stream == nullptr) {
        GlobalFree(copy);
        return nullptr;
    }
    auto bitmap = std::make_unique<Gdiplus::Bitmap>(stream);
    stream->Release();
    if (bitmap->GetLastStatus() != Gdiplus::Ok) {
        return nullptr;
    }
    return bitmap;
}

void drawText(Gdiplus::Graphics& graphics,
              const std::wstring& text,
              const Gdiplus::RectF& rect,
              const wchar_t* family,
              const Gdiplus::REAL size,
              const INT style,
              const Gdiplus::Color color,
              const Gdiplus::StringAlignment align = Gdiplus::StringAlignmentNear)
{
    Gdiplus::Font font(family, size, style, Gdiplus::UnitPixel);
    Gdiplus::SolidBrush brush(color);
    Gdiplus::StringFormat format;
    format.SetAlignment(align);
    format.SetLineAlignment(Gdiplus::StringAlignmentCenter);
    graphics.DrawString(text.c_str(), -1, &font, rect, &format, &brush);
}

void drawPanel(Gdiplus::Graphics& graphics, const Gdiplus::RectF& rect)
{
    Gdiplus::SolidBrush panel(argb(244, 5, 8, 7));
    Gdiplus::Pen border(argb(190, 0, 255, 102), 1.0f);
    graphics.FillRectangle(&panel, rect);
    graphics.DrawRectangle(&border, rect);
}

void drawProgress(Gdiplus::Graphics& graphics, const Gdiplus::RectF& rect, const double progress)
{
    Gdiplus::SolidBrush track(argb(255, 3, 8, 5));
    Gdiplus::SolidBrush fill(argb(255, 32, 220, 110));
    Gdiplus::Pen border(argb(180, 0, 255, 102), 1.0f);
    graphics.FillRectangle(&track, rect);
    graphics.DrawRectangle(&border, rect);
    Gdiplus::RectF filled = rect;
    filled.Width = std::max<Gdiplus::REAL>(2.0f, rect.Width * static_cast<Gdiplus::REAL>(std::clamp(progress, 0.0, 1.0)));
    graphics.FillRectangle(&fill, filled);
}

void paintSplash(HWND hwnd, SplashState& state, HDC hdc)
{
    RECT client{};
    GetClientRect(hwnd, &client);
    Gdiplus::Graphics graphics(hdc);
    graphics.SetSmoothingMode(Gdiplus::SmoothingModeHighQuality);
    graphics.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
    graphics.Clear(argb(255, 0, 0, 0));

    const Gdiplus::RectF bounds = rectf(client);
    Gdiplus::LinearGradientBrush glow(
        Gdiplus::PointF(0.0f, 0.0f),
        Gdiplus::PointF(bounds.Width, bounds.Height),
        argb(80, 0, 80, 45),
        argb(0, 0, 0, 0));
    graphics.FillRectangle(&glow, bounds);

    const Gdiplus::RectF art(44.0f, 44.0f, 360.0f, bounds.Height - 88.0f);
    const Gdiplus::RectF content(432.0f, 44.0f, bounds.Width - 476.0f, bounds.Height - 88.0f);
    drawPanel(graphics, art);
    drawPanel(graphics, content);

    if (state.logo != nullptr) {
        const Gdiplus::REAL logoSize = std::min<Gdiplus::REAL>(240.0f, art.Width - 86.0f);
        Gdiplus::RectF logoRect(art.X + (art.Width - logoSize) * 0.5f, art.Y + 54.0f, logoSize, logoSize);
        graphics.DrawImage(state.logo.get(), logoRect);
    }

    drawText(graphics, L"GHOSTRIGGER", Gdiplus::RectF(art.X + 16.0f, art.GetBottom() - 104.0f, art.Width - 32.0f, 42.0f),
             L"Consolas", 34.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139), Gdiplus::StringAlignmentCenter);
    drawText(graphics, L"GhostRigger (C) 2026 Shaolin (CrispyMonton).\nCo-developed by LordVaderCW.",
             Gdiplus::RectF(art.X + 18.0f, art.GetBottom() - 44.0f, art.Width - 36.0f, 36.0f),
             L"Consolas", 12.0f, Gdiplus::FontStyleRegular, argb(235, 139, 255, 190));

    drawText(graphics, L"GhostRigger", Gdiplus::RectF(content.X, content.Y + 28.0f, content.Width, 52.0f),
             L"Consolas", 44.0f, Gdiplus::FontStyleBold, argb(255, 242, 245, 243));
    drawText(graphics, L"Odyssey Engine Pipeline", Gdiplus::RectF(content.X, content.Y + 88.0f, content.Width, 34.0f),
             L"Consolas", 20.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139));
    Gdiplus::Pen line(argb(220, 0, 255, 102), 2.0f);
    graphics.DrawLine(&line, content.X, content.Y + 150.0f, content.GetRight(), content.Y + 150.0f);

    drawText(graphics, L"Opening workspace", Gdiplus::RectF(content.X, content.Y + 190.0f, content.Width, 32.0f),
             L"Consolas", 20.0f, Gdiplus::FontStyleBold, argb(255, 242, 245, 243));
    drawText(graphics, L"OK  Native runtime audit", Gdiplus::RectF(content.X, content.Y + 236.0f, content.Width, 24.0f),
             L"Consolas", 14.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139));
    drawText(graphics, L"OK  Renderer and hardware scan", Gdiplus::RectF(content.X, content.Y + 266.0f, content.Width, 24.0f),
             L"Consolas", 14.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139));
    drawText(graphics, L">  Opening workspace", Gdiplus::RectF(content.X, content.Y + 296.0f, content.Width, 24.0f),
             L"Consolas", 14.0f, Gdiplus::FontStyleBold, argb(255, 242, 245, 243));

    const Gdiplus::RectF progressRect(content.X, content.Y + 352.0f, content.Width - 72.0f, 18.0f);
    drawText(graphics, L"Starting the main window.", Gdiplus::RectF(content.X, content.Y + 324.0f, content.Width, 22.0f),
             L"Consolas", 13.0f, Gdiplus::FontStyleRegular, argb(255, 242, 245, 243));
    drawProgress(graphics, progressRect, state.progress);
    const int pct = static_cast<int>(std::round(state.progress * 100.0));
    drawText(graphics, std::to_wstring(pct) + L"%", Gdiplus::RectF(progressRect.GetRight() + 10.0f, progressRect.Y - 8.0f, 56.0f, 34.0f),
             L"Consolas", 17.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139), Gdiplus::StringAlignmentFar);

    drawText(graphics, L"LAUNCH LOG", Gdiplus::RectF(content.X, content.Y + 402.0f, content.Width, 20.0f),
             L"Consolas", 12.0f, Gdiplus::FontStyleBold, argb(255, 55, 255, 139));
    const Gdiplus::RectF logRect(content.X, content.Y + 430.0f, content.Width, std::max<Gdiplus::REAL>(60.0f, content.GetBottom() - content.Y - 438.0f));
    drawPanel(graphics, logRect);
    const std::vector<std::wstring> lines = {
        L"INFO    Native splash resources loaded from RT_RCDATA.",
        L"INFO    Renderer and hardware scan completed.",
        L"STATUS  Opening workspace: Starting the main window."
    };
    Gdiplus::REAL y = logRect.Y + 14.0f;
    for (const auto& entry : lines) {
        drawText(graphics, entry, Gdiplus::RectF(logRect.X + 12.0f, y, logRect.Width - 24.0f, 18.0f),
                 L"Consolas", 12.0f, Gdiplus::FontStyleRegular, argb(240, 196, 204, 200));
        y += 20.0f;
    }
}

LRESULT CALLBACK splashWndProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    auto* state = reinterpret_cast<SplashState*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    switch (message) {
    case WM_CREATE:
        state = reinterpret_cast<SplashState*>(reinterpret_cast<CREATESTRUCTW*>(lParam)->lpCreateParams);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(state));
        SetTimer(hwnd, kFrameTimerId, kFrameTimerMs, nullptr);
        if (state != nullptr && state->autoCloseMs > 0) {
            SetTimer(hwnd, kAutoCloseTimerId, state->autoCloseMs, nullptr);
        }
        return 0;
    case WM_TIMER:
        if (wParam == kAutoCloseTimerId) {
            DestroyWindow(hwnd);
            return 0;
        }
        if (state != nullptr) {
            const double elapsed = static_cast<double>(GetTickCount64() - state->startTick) / 1000.0;
            state->progress = std::clamp(elapsed / 4.0, 0.0, 0.92);
        }
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    case WM_PAINT:
        if (state != nullptr) {
            PAINTSTRUCT ps{};
            HDC hdc = BeginPaint(hwnd, &ps);
            paintSplash(hwnd, *state, hdc);
            EndPaint(hwnd, &ps);
            return 0;
        }
        break;
    case WM_DESTROY:
        KillTimer(hwnd, kFrameTimerId);
        KillTimer(hwnd, kAutoCloseTimerId);
        PostQuitMessage(0);
        return 0;
    default:
        break;
    }
    return DefWindowProcW(hwnd, message, wParam, lParam);
}
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int showCommand)
{
    Gdiplus::GdiplusStartupInput gdiplusInput;
    SplashState state;
    if (Gdiplus::GdiplusStartup(&state.gdiplusToken, &gdiplusInput, nullptr) != Gdiplus::Ok) {
        return 1;
    }
    state.logo = loadPngResource(IDR_SPLASH_LOGO);
    state.startTick = GetTickCount64();
    state.autoCloseMs = parseAutoCloseMs();

    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.hInstance = instance;
    wc.lpfnWndProc = splashWndProc;
    wc.lpszClassName = kWindowClassName;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(GetStockObject(BLACK_BRUSH));
    RegisterClassExW(&wc);

    const int width = 960;
    const int height = 540;
    const int x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
    const int y = (GetSystemMetrics(SM_CYSCREEN) - height) / 2;
    HWND hwnd = CreateWindowExW(
        WS_EX_TOOLWINDOW,
        kWindowClassName,
        L"GhostRigger",
        WS_POPUP,
        x,
        y,
        width,
        height,
        nullptr,
        nullptr,
        instance,
        &state);
    if (hwnd == nullptr) {
        Gdiplus::GdiplusShutdown(state.gdiplusToken);
        return 1;
    }
    ShowWindow(hwnd, showCommand);
    UpdateWindow(hwnd);

    MSG msg{};
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    Gdiplus::GdiplusShutdown(state.gdiplusToken);
    return static_cast<int>(msg.wParam);
}
