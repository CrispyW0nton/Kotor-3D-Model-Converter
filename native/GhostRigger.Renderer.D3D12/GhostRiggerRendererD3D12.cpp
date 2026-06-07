#include "GhostRiggerRendererD3D12.h"

#include "GhostRiggerRendererContracts.h"

#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <iomanip>
#include <sstream>
#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kBackendInfo =
    R"({"backend_id":"renderer_d3d12","backend_name":"GhostRigger Renderer D3D12",)"
    R"("api":"d3d12","device_luid":"","supports_hardware_rasterization":true,)"
    R"("supports_texture_arrays":true,"supports_skinned_meshes":true,)"
    R"("supports_pick_pass":true,"diagnostic_only":true})";
constexpr const char* kDeviceRequirements =
    R"({"schema":"renderer_d3d12_device_requirements.v1",)"
    R"("minimum_feature_level":"12_0","requires_dxgi_factory":true,)"
    R"("requires_command_queue":true,"requires_swap_chain":true,)"
    R"("requires_descriptor_heaps":["cbv_srv_uav","rtv","dsv"],)"
    R"("phase":"P1 diagnostic boundary"})";
constexpr const char* kDryRunFrameStats =
    R"({"frame_index":0,"backend_id":"renderer_d3d12","surface_id":"diagnostic",)"
    R"("draw_count":0,"triangle_count":0,"cpu_submit_ms":0.0,"gpu_frame_ms":0.0})";

std::string json_escape(const std::wstring& value) {
    std::ostringstream stream;
    for (wchar_t ch : value) {
        if (ch == L'\\') {
            stream << "\\\\";
        } else if (ch == L'"') {
            stream << "\\\"";
        } else if (ch >= 0x20 && ch <= 0x7e) {
            stream << static_cast<char>(ch);
        } else {
            stream << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                   << static_cast<unsigned int>(ch) << std::dec << std::setfill(' ');
        }
    }
    return stream.str();
}

std::string hresult_hex(HRESULT hr) {
    std::ostringstream stream;
    stream << "0x" << std::uppercase << std::hex << static_cast<unsigned long>(hr);
    return stream.str();
}

} // namespace

extern "C" {

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_version() {
    return kVersion;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_capabilities_json() {
    static const char* capabilities =
        R"({"name":"GhostRigger.Renderer.D3D12","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"d3d12",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Renderer.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = capabilities;
    payload += gr_renderer_contracts_version();
    payload += R"(","supports_hardware_rasterization":true,)"
               R"("supports_texture_arrays":true,"supports_skinned_meshes":true,)"
               R"("supports_pick_pass":true})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_device_requirements_json() {
    return kDeviceRequirements;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_adapter_probe_json() {
    static thread_local std::string payload;
    payload =
        R"({"schema":"renderer_d3d12_adapter_probe.v1","backend_id":"renderer_d3d12",)"
        R"("diagnostic_only":true,"adapters":[)";

    Microsoft::WRL::ComPtr<IDXGIFactory6> factory;
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        payload += R"(],"status":"factory_error","hresult":")";
        payload += hresult_hex(hr);
        payload += R"("})";
        return payload.c_str();
    }

    unsigned int adapter_count = 0;
    for (UINT index = 0;; ++index) {
        Microsoft::WRL::ComPtr<IDXGIAdapter1> adapter;
        hr = factory->EnumAdapters1(index, &adapter);
        if (hr == DXGI_ERROR_NOT_FOUND) {
            break;
        }
        if (FAILED(hr)) {
            payload += R"(],"status":"adapter_error","hresult":")";
            payload += hresult_hex(hr);
            payload += R"("})";
            return payload.c_str();
        }

        DXGI_ADAPTER_DESC1 desc{};
        hr = adapter->GetDesc1(&desc);
        if (FAILED(hr)) {
            continue;
        }

        if (adapter_count > 0) {
            payload += ",";
        }
        payload += R"({"index":)";
        payload += std::to_string(index);
        payload += R"(,"description":")";
        payload += json_escape(desc.Description);
        payload += R"(","vendor_id":)";
        payload += std::to_string(desc.VendorId);
        payload += R"(,"device_id":)";
        payload += std::to_string(desc.DeviceId);
        payload += R"(,"dedicated_video_memory":)";
        payload += std::to_string(static_cast<unsigned long long>(desc.DedicatedVideoMemory));
        payload += R"(,"software":)";
        payload += (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) ? "true" : "false";
        payload += "}";
        ++adapter_count;
    }

    payload += R"(],"status":"ok","adapter_count":)";
    payload += std::to_string(adapter_count);
    payload += "}";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_device_readiness_json() {
    static thread_local std::string payload;
    payload =
        R"({"schema":"renderer_d3d12_device_readiness.v1","backend_id":"renderer_d3d12",)"
        R"("diagnostic_only":true,"feature_level":"12_0","draw_submission_enabled":false,)"
        R"("devices":[)";

    Microsoft::WRL::ComPtr<IDXGIFactory6> factory;
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        payload += R"(],"status":"factory_error","hresult":")";
        payload += hresult_hex(hr);
        payload += R"("})";
        return payload.c_str();
    }

    unsigned int checked_count = 0;
    unsigned int ready_count = 0;
    for (UINT index = 0;; ++index) {
        Microsoft::WRL::ComPtr<IDXGIAdapter1> adapter;
        hr = factory->EnumAdapters1(index, &adapter);
        if (hr == DXGI_ERROR_NOT_FOUND) {
            break;
        }
        if (FAILED(hr)) {
            payload += R"(],"status":"adapter_error","hresult":")";
            payload += hresult_hex(hr);
            payload += R"("})";
            return payload.c_str();
        }

        DXGI_ADAPTER_DESC1 desc{};
        hr = adapter->GetDesc1(&desc);
        if (FAILED(hr) || (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE)) {
            continue;
        }

        if (checked_count > 0) {
            payload += ",";
        }
        payload += R"({"index":)";
        payload += std::to_string(index);
        payload += R"(,"description":")";
        payload += json_escape(desc.Description);
        payload += R"(","vendor_id":)";
        payload += std::to_string(desc.VendorId);
        payload += R"(,"device_id":)";
        payload += std::to_string(desc.DeviceId);

        hr = D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_12_0, __uuidof(ID3D12Device), nullptr);
        const bool device_ready = SUCCEEDED(hr);
        if (device_ready) {
            ++ready_count;
        }

        payload += R"(,"device_ready":)";
        payload += device_ready ? "true" : "false";
        payload += R"(,"hresult":")";
        payload += hresult_hex(hr);
        payload += R"(","retained_device":false})";
        ++checked_count;
    }

    payload += R"(],"status":"ok","checked_adapter_count":)";
    payload += std::to_string(checked_count);
    payload += R"(,"ready_adapter_count":)";
    payload += std::to_string(ready_count);
    payload += "}";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_failure_diagnostics_json() {
    static thread_local std::string payload;
    payload =
        R"({"schema":"renderer_d3d12_failure_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,)"
        R"("failure_points":["dxgi_factory","adapter_enumeration","feature_level",)"
        R"("device_creation","command_queue","swap_chain"],)"
        R"("draw_submission_enabled":false,"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_dry_run_frame_stats_json() {
    return kDryRunFrameStats;
}

}
