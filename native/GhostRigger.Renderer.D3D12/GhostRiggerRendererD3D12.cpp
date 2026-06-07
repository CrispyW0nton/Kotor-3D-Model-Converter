#include "GhostRiggerRendererD3D12.h"

#include "GhostRiggerRendererContracts.h"

#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <iomanip>
#include <memory>
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

struct DiagnosticContext {
    Microsoft::WRL::ComPtr<ID3D12Device> device;
    Microsoft::WRL::ComPtr<ID3D12CommandQueue> command_queue;
    Microsoft::WRL::ComPtr<ID3D12DescriptorHeap> cbv_srv_uav_heap;
    Microsoft::WRL::ComPtr<ID3D12DescriptorHeap> rtv_heap;
    Microsoft::WRL::ComPtr<ID3D12DescriptorHeap> dsv_heap;
    Microsoft::WRL::ComPtr<ID3D12CommandAllocator> command_allocator;
    Microsoft::WRL::ComPtr<ID3D12GraphicsCommandList> command_list;
    std::string adapter_description;
    HRESULT device_hr = E_FAIL;
    HRESULT queue_hr = E_FAIL;
    HRESULT cbv_srv_uav_heap_hr = E_FAIL;
    HRESULT rtv_heap_hr = E_FAIL;
    HRESULT dsv_heap_hr = E_FAIL;
    HRESULT command_allocator_hr = E_FAIL;
    HRESULT command_list_hr = E_FAIL;
    HRESULT command_list_close_hr = E_FAIL;
    bool device_ready = false;
    bool command_queue_ready = false;
    bool descriptor_heaps_ready = false;
    bool command_allocator_ready = false;
    bool command_list_ready = false;
    bool command_list_closed = false;
    bool surface_handle_ready = false;
    bool swap_chain_ready = false;
    bool render_target_metadata_ready = false;
    bool barrier_clear_pass_metadata_ready = false;
    bool command_recording_dry_run_ready = false;
    bool draw_submission_enabled = false;
};

DiagnosticContext* context_from_handle(void* context) {
    return static_cast<DiagnosticContext*>(context);
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

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_queue_swap_chain_readiness_json() {
    static thread_local std::string payload;
    payload =
        R"({"schema":"renderer_d3d12_queue_swap_chain_readiness.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,)"
        R"("draw_submission_enabled":false,"command_queue_created":false,)"
        R"("swap_chain_created":false,"requires_device_ready":true,)"
        R"("queue_desc":{"type":"direct","priority":"normal","flags":"none","node_mask":0},)"
        R"("swap_chain_desc":{"buffer_count":2,"format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
        R"("swap_effect":"DXGI_SWAP_EFFECT_FLIP_DISCARD","sample_count":1},)"
        R"("failure_points":["device_not_ready","command_queue_create",)"
        R"("window_handle_missing","swap_chain_create","present_mode_unsupported"],)"
        R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_descriptor_allocator_readiness_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_descriptor_allocator_readiness.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_device":false,"descriptor_heaps_ready":false,"command_allocator_ready":false,"command_list_created":false,"draw_submission_enabled":false})";
    }

    payload =
        R"({"schema":"renderer_d3d12_descriptor_allocator_readiness.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"cbv_srv_uav_heap_ready":)";
    payload += target->cbv_srv_uav_heap ? "true" : "false";
    payload += R"(,"rtv_heap_ready":)";
    payload += target->rtv_heap ? "true" : "false";
    payload += R"(,"dsv_heap_ready":)";
    payload += target->dsv_heap ? "true" : "false";
    payload += R"(,"descriptor_heaps_ready":)";
    payload += target->descriptor_heaps_ready ? "true" : "false";
    payload += R"(,"command_allocator_ready":)";
    payload += target->command_allocator_ready ? "true" : "false";
    payload += R"(,"command_list_created":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"cbv_srv_uav_heap_hresult":")";
    payload += hresult_hex(target->cbv_srv_uav_heap_hr);
    payload += R"(","rtv_heap_hresult":")";
    payload += hresult_hex(target->rtv_heap_hr);
    payload += R"(","dsv_heap_hresult":")";
    payload += hresult_hex(target->dsv_heap_hr);
    payload += R"(","command_allocator_hresult":")";
    payload += hresult_hex(target->command_allocator_hr);
    payload += R"("})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_command_list_readiness_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_command_list_readiness.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_device":false,"command_allocator_ready":false,"command_list_ready":false,"command_list_closed":false,"command_list_executed":false,"draw_submission_enabled":false})";
    }

    payload =
        R"({"schema":"renderer_d3d12_command_list_readiness.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_allocator":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"command_allocator_ready":)";
    payload += target->command_allocator_ready ? "true" : "false";
    payload += R"(,"command_list_ready":)";
    payload += target->command_list_ready ? "true" : "false";
    payload += R"(,"command_list_closed":)";
    payload += target->command_list_closed ? "true" : "false";
    payload += R"(,"command_list_type":"direct","initial_pipeline_state":false,)"
               R"("app_commands_recorded":false,"command_list_executed":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"command_allocator_hresult":")";
    payload += hresult_hex(target->command_allocator_hr);
    payload += R"(","command_list_hresult":")";
    payload += hresult_hex(target->command_list_hr);
    payload += R"(","command_list_close_hresult":")";
    payload += hresult_hex(target->command_list_close_hr);
    payload += R"("})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_surface_swap_chain_readiness_json(
    void* context,
    void* native_window_handle
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_surface_swap_chain_readiness.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_device":false,"retained_command_queue":false,"native_window_handle_ready":false,"swap_chain_created":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool native_window_handle_ready = native_window_handle != nullptr;
    const bool prerequisites_ready =
        target->device_ready && target->command_queue_ready && native_window_handle_ready;

    payload =
        R"({"schema":"renderer_d3d12_surface_swap_chain_readiness.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"native_window_handle_ready":)";
    payload += native_window_handle_ready ? "true" : "false";
    payload += R"(,"surface_handle_type":"HWND","surface_handle_owned_by_host":false,)"
               R"("requires_host_window":true,"prerequisites_ready":)";
    payload += prerequisites_ready ? "true" : "false";
    payload += R"(,"swap_chain_created":false,"swap_chain_ready":false,)"
               R"("present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"swap_chain_desc":{"buffer_count":2,)"
               R"("format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
               R"("swap_effect":"DXGI_SWAP_EFFECT_FLIP_DISCARD",)"
               R"("sample_count":1,"allow_tearing_probe":false},)"
               R"("failure_points":["native_window_handle_missing",)"
               R"("device_not_ready","command_queue_not_ready","swap_chain_create_skipped"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_render_target_metadata_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_render_target_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_device":false,"rtv_heap_ready":false,"swap_chain_created":false,"back_buffers_acquired":false,"render_target_views_created":false,"draw_submission_enabled":false})";
    }

    unsigned int rtv_descriptor_increment_size = 0;
    if (target->device) {
        rtv_descriptor_increment_size = target->device->GetDescriptorHandleIncrementSize(
            D3D12_DESCRIPTOR_HEAP_TYPE_RTV
        );
    }

    payload =
        R"({"schema":"renderer_d3d12_render_target_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"rtv_heap_ready":)";
    payload += target->rtv_heap ? "true" : "false";
    payload += R"(,"rtv_heap_descriptor_capacity":8,"rtv_descriptor_increment_size":)";
    payload += std::to_string(rtv_descriptor_increment_size);
    payload += R"(,"expected_back_buffer_count":2,)"
               R"("back_buffer_format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
               R"("back_buffer_state_before_present":"D3D12_RESOURCE_STATE_RENDER_TARGET",)"
               R"("back_buffer_state_after_present":"D3D12_RESOURCE_STATE_PRESENT",)"
               R"("swap_chain_created":false,"back_buffers_acquired":false,)"
               R"("render_target_views_created":false,"render_target_bound":false,)"
               R"("clear_enabled":false,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_barrier_clear_pass_metadata_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_barrier_clear_pass_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_device":false,"retained_command_list":false,"resource_barriers_recorded":false,"clear_recorded":false,"command_list_executed":false,"draw_submission_enabled":false})";
    }

    payload =
        R"({"schema":"renderer_d3d12_barrier_clear_pass_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"command_list_closed":)";
    payload += target->command_list_closed ? "true" : "false";
    payload += R"(,"expected_back_buffer_count":2,)"
               R"("barrier_sequence":[{"from":"D3D12_RESOURCE_STATE_PRESENT",)"
               R"("to":"D3D12_RESOURCE_STATE_RENDER_TARGET"},)"
               R"({"from":"D3D12_RESOURCE_STATE_RENDER_TARGET",)"
               R"("to":"D3D12_RESOURCE_STATE_PRESENT"}],)"
               R"("resource_barriers_recorded":false,)"
               R"("clear_pass":{"format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
               R"("clear_color":[0.0,0.0,0.0,1.0],"clear_recorded":false},)"
               R"("render_target_bound":false,"present_enabled":false,)"
               R"("command_list_executed":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_command_recording_dry_run_frame_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_command_recording_dry_run_frame.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_command_allocator":false,"retained_command_list":false,"command_allocator_reset":false,"command_list_reset":false,"resource_barriers_recorded":false,"clear_recorded":false,"draw_calls_recorded":0,"command_list_closed_for_execute":false,"command_list_executed":false,"draw_submission_enabled":false})";
    }

    payload =
        R"({"schema":"renderer_d3d12_command_recording_dry_run_frame.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_command_allocator":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"command_list_initially_closed":)";
    payload += target->command_list_closed ? "true" : "false";
    payload += R"(,"frame_index":0,"expected_back_buffer_index":0,)"
               R"("command_allocator_reset":false,"command_list_reset":false,)"
               R"("resource_barriers_recorded":false,"clear_recorded":false,)"
               R"("render_target_bound":false,"draw_calls_recorded":0,)"
               R"("triangle_count":0,"descriptor_tables_bound":false,)"
               R"("pipeline_state_bound":false,"root_signature_bound":false,)"
               R"("command_list_closed_for_execute":false,)"
               R"("command_list_executed":false,"present_enabled":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_failure_diagnostics_json() {
    static thread_local std::string payload;
    payload =
        R"({"schema":"renderer_d3d12_failure_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,)"
        R"("failure_points":["dxgi_factory","adapter_enumeration","feature_level",)"
        R"("device_creation","command_queue","native_window_handle","swap_chain",)"
        R"("render_target_metadata","barrier_clear_pass_metadata",)"
        R"("command_recording_dry_run"],)"
        R"("draw_submission_enabled":false,"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_dry_run_frame_stats_json() {
    return kDryRunFrameStats;
}

GR_RENDERER_D3D12_API void* gr_renderer_d3d12_create_diagnostic_context() {
    auto context = std::make_unique<DiagnosticContext>();

    Microsoft::WRL::ComPtr<IDXGIFactory6> factory;
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        context->device_hr = hr;
        context->queue_hr = hr;
        return context.release();
    }

    for (UINT index = 0;; ++index) {
        Microsoft::WRL::ComPtr<IDXGIAdapter1> adapter;
        hr = factory->EnumAdapters1(index, &adapter);
        if (hr == DXGI_ERROR_NOT_FOUND) {
            context->device_hr = DXGI_ERROR_NOT_FOUND;
            context->queue_hr = DXGI_ERROR_NOT_FOUND;
            return context.release();
        }
        if (FAILED(hr)) {
            context->device_hr = hr;
            context->queue_hr = hr;
            return context.release();
        }

        DXGI_ADAPTER_DESC1 desc{};
        hr = adapter->GetDesc1(&desc);
        if (FAILED(hr) || (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE)) {
            continue;
        }

        context->adapter_description = json_escape(desc.Description);
        hr = D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&context->device));
        context->device_hr = hr;
        context->device_ready = SUCCEEDED(hr);
        if (!context->device_ready) {
            continue;
        }

        D3D12_COMMAND_QUEUE_DESC queue_desc{};
        queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
        queue_desc.Priority = D3D12_COMMAND_QUEUE_PRIORITY_NORMAL;
        queue_desc.Flags = D3D12_COMMAND_QUEUE_FLAG_NONE;
        queue_desc.NodeMask = 0;
        hr = context->device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&context->command_queue));
        context->queue_hr = hr;
        context->command_queue_ready = SUCCEEDED(hr);

        D3D12_DESCRIPTOR_HEAP_DESC descriptor_heap_desc{};
        descriptor_heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
        descriptor_heap_desc.NumDescriptors = 64;
        descriptor_heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
        descriptor_heap_desc.NodeMask = 0;
        hr = context->device->CreateDescriptorHeap(
            &descriptor_heap_desc,
            IID_PPV_ARGS(&context->cbv_srv_uav_heap)
        );
        context->cbv_srv_uav_heap_hr = hr;

        descriptor_heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
        descriptor_heap_desc.NumDescriptors = 8;
        descriptor_heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_NONE;
        hr = context->device->CreateDescriptorHeap(&descriptor_heap_desc, IID_PPV_ARGS(&context->rtv_heap));
        context->rtv_heap_hr = hr;

        descriptor_heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV;
        descriptor_heap_desc.NumDescriptors = 8;
        hr = context->device->CreateDescriptorHeap(&descriptor_heap_desc, IID_PPV_ARGS(&context->dsv_heap));
        context->dsv_heap_hr = hr;

        context->descriptor_heaps_ready =
            context->cbv_srv_uav_heap != nullptr && context->rtv_heap != nullptr && context->dsv_heap != nullptr;

        hr = context->device->CreateCommandAllocator(
            D3D12_COMMAND_LIST_TYPE_DIRECT,
            IID_PPV_ARGS(&context->command_allocator)
        );
        context->command_allocator_hr = hr;
        context->command_allocator_ready = SUCCEEDED(hr);
        if (context->command_allocator_ready) {
            hr = context->device->CreateCommandList(
                0,
                D3D12_COMMAND_LIST_TYPE_DIRECT,
                context->command_allocator.Get(),
                nullptr,
                IID_PPV_ARGS(&context->command_list)
            );
            context->command_list_hr = hr;
            context->command_list_ready = SUCCEEDED(hr);
            if (context->command_list_ready) {
                hr = context->command_list->Close();
                context->command_list_close_hr = hr;
                context->command_list_closed = SUCCEEDED(hr);
            }
        }
        return context.release();
    }
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_diagnostic_context_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_diagnostic_context.v1","backend_id":"renderer_d3d12","status":"null_context","device_ready":false,"command_queue_ready":false,"draw_submission_enabled":false})";
    }

    payload =
        R"({"schema":"renderer_d3d12_diagnostic_context.v1","backend_id":"renderer_d3d12",)"
        R"("diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"retained_cbv_srv_uav_heap":)";
    payload += target->cbv_srv_uav_heap ? "true" : "false";
    payload += R"(,"retained_rtv_heap":)";
    payload += target->rtv_heap ? "true" : "false";
    payload += R"(,"retained_dsv_heap":)";
    payload += target->dsv_heap ? "true" : "false";
    payload += R"(,"retained_command_allocator":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"device_ready":)";
    payload += target->device_ready ? "true" : "false";
    payload += R"(,"command_queue_ready":)";
    payload += target->command_queue_ready ? "true" : "false";
    payload += R"(,"descriptor_heaps_ready":)";
    payload += target->descriptor_heaps_ready ? "true" : "false";
    payload += R"(,"command_allocator_ready":)";
    payload += target->command_allocator_ready ? "true" : "false";
    payload += R"(,"command_list_ready":)";
    payload += target->command_list_ready ? "true" : "false";
    payload += R"(,"command_list_closed":)";
    payload += target->command_list_closed ? "true" : "false";
    payload += R"(,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"swap_chain_created":false,"command_list_created":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"command_list_executed":false,"adapter_description":")";
    payload += target->adapter_description;
    payload += R"(","surface_handle_ready":)";
    payload += target->surface_handle_ready ? "true" : "false";
    payload += R"(,"swap_chain_ready":)";
    payload += target->swap_chain_ready ? "true" : "false";
    payload += R"(,"render_target_metadata_ready":)";
    payload += target->render_target_metadata_ready ? "true" : "false";
    payload += R"(,"barrier_clear_pass_metadata_ready":)";
    payload += target->barrier_clear_pass_metadata_ready ? "true" : "false";
    payload += R"(,"command_recording_dry_run_ready":)";
    payload += target->command_recording_dry_run_ready ? "true" : "false";
    payload += R"(,"device_hresult":")";
    payload += hresult_hex(target->device_hr);
    payload += R"(","command_queue_hresult":")";
    payload += hresult_hex(target->queue_hr);
    payload += R"(","cbv_srv_uav_heap_hresult":")";
    payload += hresult_hex(target->cbv_srv_uav_heap_hr);
    payload += R"(","rtv_heap_hresult":")";
    payload += hresult_hex(target->rtv_heap_hr);
    payload += R"(","dsv_heap_hresult":")";
    payload += hresult_hex(target->dsv_heap_hr);
    payload += R"(","command_allocator_hresult":")";
    payload += hresult_hex(target->command_allocator_hr);
    payload += R"(","command_list_hresult":")";
    payload += hresult_hex(target->command_list_hr);
    payload += R"(","command_list_close_hresult":")";
    payload += hresult_hex(target->command_list_close_hr);
    payload += R"("})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API void gr_renderer_d3d12_destroy_diagnostic_context(void* context) {
    delete context_from_handle(context);
}

}
