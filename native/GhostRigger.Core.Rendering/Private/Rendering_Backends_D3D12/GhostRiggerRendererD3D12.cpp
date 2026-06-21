#include "GhostRiggerPythonPayloadResource.h"
#include "Rendering_Backends_D3D12/GhostRiggerRendererD3D12.h"

#include "GhostRiggerRendererContracts.h"

#include <windows.h>

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
    Microsoft::WRL::ComPtr<ID3D12Fence> no_draw_fence;
    Microsoft::WRL::ComPtr<ID3D12Fence> guarded_clear_pass_fence;
    Microsoft::WRL::ComPtr<IDXGISwapChain3> guarded_swap_chain;
    Microsoft::WRL::ComPtr<ID3D12Resource> guarded_back_buffer_0;
    Microsoft::WRL::ComPtr<ID3D12Resource> guarded_back_buffer_1;
    std::string adapter_description;
    HRESULT device_hr = E_FAIL;
    HRESULT queue_hr = E_FAIL;
    HRESULT cbv_srv_uav_heap_hr = E_FAIL;
    HRESULT rtv_heap_hr = E_FAIL;
    HRESULT dsv_heap_hr = E_FAIL;
    HRESULT command_allocator_hr = E_FAIL;
    HRESULT command_list_hr = E_FAIL;
    HRESULT command_list_close_hr = E_FAIL;
    HRESULT guarded_allocator_reset_hr = E_FAIL;
    HRESULT guarded_command_list_reset_hr = E_FAIL;
    HRESULT guarded_command_list_close_hr = E_FAIL;
    HRESULT no_draw_fence_hr = E_FAIL;
    HRESULT no_draw_signal_hr = E_FAIL;
    HRESULT no_draw_set_event_hr = E_FAIL;
    HRESULT guarded_swap_chain_factory_hr = E_FAIL;
    HRESULT guarded_swap_chain_create_hr = E_FAIL;
    HRESULT guarded_swap_chain_query_hr = E_FAIL;
    HRESULT guarded_back_buffer_0_hr = E_FAIL;
    HRESULT guarded_back_buffer_1_hr = E_FAIL;
    HRESULT guarded_barrier_clear_allocator_reset_hr = E_FAIL;
    HRESULT guarded_barrier_clear_command_list_reset_hr = E_FAIL;
    HRESULT guarded_barrier_clear_command_list_close_hr = E_FAIL;
    HRESULT guarded_clear_pass_fence_hr = E_FAIL;
    HRESULT guarded_clear_pass_signal_hr = E_FAIL;
    HRESULT guarded_clear_pass_set_event_hr = E_FAIL;
    HRESULT guarded_present_hr = E_FAIL;
    DWORD no_draw_wait_result = WAIT_FAILED;
    DWORD guarded_clear_pass_wait_result = WAIT_FAILED;
    UINT64 no_draw_fence_value = 1;
    UINT64 guarded_clear_pass_fence_value = 1;
    UINT64 diagnostic_frame_index = 0;
    UINT64 diagnostic_presented_frame_count = 0;
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
    bool guarded_allocator_reset = false;
    bool guarded_command_list_reset = false;
    bool guarded_command_list_closed = false;
    bool no_draw_command_list_executed = false;
    bool no_draw_fence_ready = false;
    bool no_draw_fence_signaled = false;
    bool no_draw_fence_completed = false;
    bool no_draw_fence_waited = false;
    bool present_readiness_metadata_ready = false;
    bool guarded_swap_chain_native_window_handle_ready = false;
    bool guarded_swap_chain_create_attempted = false;
    bool guarded_swap_chain_created = false;
    bool guarded_back_buffers_acquired = false;
    bool guarded_render_target_views_created = false;
    bool guarded_barrier_clear_attempted = false;
    bool guarded_resource_barriers_recorded = false;
    bool guarded_clear_recorded = false;
    bool guarded_barrier_clear_command_list_closed = false;
    bool guarded_clear_pass_command_list_executed = false;
    bool guarded_clear_pass_fence_ready = false;
    bool guarded_clear_pass_fence_signaled = false;
    bool guarded_clear_pass_fence_completed = false;
    bool guarded_clear_pass_fence_waited = false;
    bool post_clear_present_readiness_metadata_ready = false;
    bool guarded_present_ready = false;
    bool guarded_present_called = false;
    bool guarded_present_succeeded = false;
    bool post_present_frame_accounting_ready = false;
    bool draw_list_readiness_metadata_ready = false;
    bool resource_binding_readiness_metadata_ready = false;
    bool pipeline_state_readiness_metadata_ready = false;
    bool guarded_shader_bytecode_metadata_ready = false;
    bool shader_reflection_input_layout_metadata_ready = false;
    bool guarded_root_signature_metadata_ready = false;
    bool guarded_pipeline_state_object_metadata_ready = false;
    bool guarded_draw_command_recording_metadata_ready = false;
    bool guarded_draw_submission_readiness_metadata_ready = false;
    bool guarded_post_draw_frame_accounting_readiness_metadata_ready = false;
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
        R"({"name":"GhostRigger.Core.Rendering","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"d3d12",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Core.Rendering",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = capabilities;
    payload += gr_renderer_contracts_version();
    payload += R"(","supports_hardware_rasterization":true,)"
               R"("supports_texture_arrays":true,"supports_skinned_meshes":true,)"
               R"("supports_pick_pass":true,"draw_submission_enabled":false,)"
               R"("guarded_metadata_capabilities":[)"
               R"("descriptor_allocator_readiness",)"
               R"("command_list_readiness",)"
               R"("surface_swap_chain_readiness",)"
               R"("render_target_metadata",)"
               R"("barrier_clear_pass_metadata",)"
               R"("command_recording_dry_run_frame",)"
               R"("guarded_command_recording_diagnostics",)"
               R"("no_draw_execution_fence_diagnostics",)"
               R"("present_readiness_metadata",)"
               R"("guarded_swap_chain_creation_diagnostics",)"
               R"("guarded_back_buffer_rtv_diagnostics",)"
               R"("guarded_barrier_clear_recording_diagnostics",)"
               R"("guarded_clear_pass_execution_fence_diagnostics",)"
               R"("post_clear_present_readiness_diagnostics",)"
               R"("guarded_present_call_diagnostics",)"
               R"("post_present_frame_accounting_diagnostics",)"
               R"("draw_list_readiness_metadata",)"
               R"("resource_binding_readiness_metadata",)"
               R"("pipeline_state_readiness_metadata",)"
               R"("guarded_shader_bytecode_metadata",)"
               R"("shader_reflection_input_layout_metadata",)"
               R"("guarded_root_signature_metadata",)"
               R"("guarded_pipeline_state_object_metadata",)"
               R"("guarded_draw_command_recording_metadata",)"
               R"("guarded_draw_submission_readiness_metadata",)"
               R"("guarded_post_draw_frame_accounting_readiness_metadata"]})";
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

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_command_recording_diagnostics_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_command_recording_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"allocator_reset":false,"command_list_reset":false,"command_list_closed":false,"resource_barriers_recorded":false,"clear_recorded":false,"draw_calls_recorded":0,"command_list_executed":false,"draw_submission_enabled":false})";
    }

    if (target->command_allocator && target->command_list && !target->guarded_command_list_closed) {
        HRESULT hr = target->command_allocator->Reset();
        target->guarded_allocator_reset_hr = hr;
        target->guarded_allocator_reset = SUCCEEDED(hr);

        if (target->guarded_allocator_reset) {
            hr = target->command_list->Reset(target->command_allocator.Get(), nullptr);
            target->guarded_command_list_reset_hr = hr;
            target->guarded_command_list_reset = SUCCEEDED(hr);
        }

        if (target->guarded_command_list_reset) {
            hr = target->command_list->Close();
            target->guarded_command_list_close_hr = hr;
            target->guarded_command_list_closed = SUCCEEDED(hr);
        }
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_command_recording_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_command_allocator":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"allocator_reset":)";
    payload += target->guarded_allocator_reset ? "true" : "false";
    payload += R"(,"command_list_reset":)";
    payload += target->guarded_command_list_reset ? "true" : "false";
    payload += R"(,"command_list_closed":)";
    payload += target->guarded_command_list_closed ? "true" : "false";
    payload += R"(,"resource_barriers_recorded":false,"clear_recorded":false,)"
               R"("render_target_bound":false,"draw_calls_recorded":0,)"
               R"("command_list_executed":false,"present_enabled":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"allocator_reset_hresult":")";
    payload += hresult_hex(target->guarded_allocator_reset_hr);
    payload += R"(","command_list_reset_hresult":")";
    payload += hresult_hex(target->guarded_command_list_reset_hr);
    payload += R"(","command_list_close_hresult":")";
    payload += hresult_hex(target->guarded_command_list_close_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_no_draw_execution_fence_diagnostics_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_no_draw_execution_fence_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_command_queue":false,"retained_command_list":false,"no_draw_command_list_executed":false,"draw_calls_recorded":0,"command_lists_submitted":0,"fence_created":false,"fence_signaled":false,"fence_completed":false,"fence_waited":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    if (target->command_queue && target->command_list && !target->no_draw_fence_completed) {
        if (!target->guarded_command_list_closed && !target->command_list_closed) {
            HRESULT hr = target->command_list->Close();
            target->guarded_command_list_close_hr = hr;
            target->guarded_command_list_closed = SUCCEEDED(hr);
            target->command_list_closed = target->guarded_command_list_closed;
        }

        if (target->guarded_command_list_closed || target->command_list_closed) {
            ID3D12CommandList* command_lists[] = { target->command_list.Get() };
            target->command_queue->ExecuteCommandLists(1, command_lists);
            target->no_draw_command_list_executed = true;

            HRESULT hr = target->device
                ? target->device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&target->no_draw_fence))
                : E_FAIL;
            target->no_draw_fence_hr = hr;
            target->no_draw_fence_ready = SUCCEEDED(hr);

            if (target->no_draw_fence_ready) {
                hr = target->command_queue->Signal(target->no_draw_fence.Get(), target->no_draw_fence_value);
                target->no_draw_signal_hr = hr;
                target->no_draw_fence_signaled = SUCCEEDED(hr);
            }

            if (
                target->no_draw_fence_signaled &&
                target->no_draw_fence->GetCompletedValue() < target->no_draw_fence_value
            ) {
                HANDLE fence_event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
                if (fence_event != nullptr) {
                    hr = target->no_draw_fence->SetEventOnCompletion(target->no_draw_fence_value, fence_event);
                    target->no_draw_set_event_hr = hr;
                    if (SUCCEEDED(hr)) {
                        target->no_draw_wait_result = WaitForSingleObject(fence_event, 2000);
                        target->no_draw_fence_waited = target->no_draw_wait_result == WAIT_OBJECT_0;
                    }
                    CloseHandle(fence_event);
                } else {
                    target->no_draw_set_event_hr = HRESULT_FROM_WIN32(GetLastError());
                }
            } else if (target->no_draw_fence_signaled) {
                target->no_draw_set_event_hr = S_OK;
                target->no_draw_wait_result = WAIT_OBJECT_0;
            }

            target->no_draw_fence_completed =
                target->no_draw_fence_signaled &&
                target->no_draw_fence->GetCompletedValue() >= target->no_draw_fence_value;
        }
    }

    payload =
        R"({"schema":"renderer_d3d12_no_draw_execution_fence_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"no_draw_command_list_executed":)";
    payload += target->no_draw_command_list_executed ? "true" : "false";
    payload += R"(,"draw_calls_recorded":0,"command_lists_submitted":)";
    payload += target->no_draw_command_list_executed ? "1" : "0";
    payload += R"(,"fence_created":)";
    payload += target->no_draw_fence_ready ? "true" : "false";
    payload += R"(,"fence_signaled":)";
    payload += target->no_draw_fence_signaled ? "true" : "false";
    payload += R"(,"fence_completed":)";
    payload += target->no_draw_fence_completed ? "true" : "false";
    payload += R"(,"fence_waited":)";
    payload += target->no_draw_fence_waited ? "true" : "false";
    payload += R"(,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"fence_value":)";
    payload += std::to_string(static_cast<unsigned long long>(target->no_draw_fence_value));
    payload += R"(,"wait_result":)";
    payload += std::to_string(static_cast<unsigned long>(target->no_draw_wait_result));
    payload += R"(,"fence_hresult":")";
    payload += hresult_hex(target->no_draw_fence_hr);
    payload += R"(","signal_hresult":")";
    payload += hresult_hex(target->no_draw_signal_hr);
    payload += R"(","set_event_hresult":")";
    payload += hresult_hex(target->no_draw_set_event_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_present_readiness_metadata_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_present_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_command_queue":false,"swap_chain_created":false,"back_buffers_acquired":false,"present_ready":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool retained_command_queue = target->command_queue != nullptr;
    const bool fence_completed = target->no_draw_fence_completed;
    const bool present_ready = false;
    target->present_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_present_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += retained_command_queue ? "true" : "false";
    payload += R"(,"no_draw_fence_completed":)";
    payload += fence_completed ? "true" : "false";
    payload += R"(,"swap_chain_created":false,"swap_chain_ready":false,)"
               R"("back_buffers_acquired":false,"render_target_views_created":false,)"
               R"("back_buffer_index_known":false,"present_ready":)";
    payload += present_ready ? "true" : "false";
    payload += R"(,"present_called":false,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"present_desc":{"sync_interval":1,"flags":"DXGI_PRESENT_NONE",)"
               R"("swap_effect":"DXGI_SWAP_EFFECT_FLIP_DISCARD",)"
               R"("requires_transition_to_present":true},)"
               R"("failure_points":["swap_chain_missing","back_buffers_missing",)"
               R"("rtv_missing","resource_transition_not_recorded",)"
               R"("present_call_disabled"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_swap_chain_creation_diagnostics_json(
    void* context,
    void* native_window_handle
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_swap_chain_creation_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"native_window_handle_ready":false,"retained_device":false,"retained_command_queue":false,"swap_chain_create_attempted":false,"swap_chain_created":false,"back_buffers_acquired":false,"render_target_views_created":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    target->guarded_swap_chain_native_window_handle_ready = native_window_handle != nullptr;
    const bool prerequisites_ready =
        target->device != nullptr &&
        target->command_queue != nullptr &&
        target->guarded_swap_chain_native_window_handle_ready;

    if (prerequisites_ready && !target->guarded_swap_chain_created) {
        Microsoft::WRL::ComPtr<IDXGIFactory6> factory;
        HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
        target->guarded_swap_chain_factory_hr = hr;

        if (SUCCEEDED(hr)) {
            DXGI_SWAP_CHAIN_DESC1 swap_chain_desc{};
            swap_chain_desc.Width = 0;
            swap_chain_desc.Height = 0;
            swap_chain_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
            swap_chain_desc.Stereo = FALSE;
            swap_chain_desc.SampleDesc.Count = 1;
            swap_chain_desc.SampleDesc.Quality = 0;
            swap_chain_desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
            swap_chain_desc.BufferCount = 2;
            swap_chain_desc.Scaling = DXGI_SCALING_STRETCH;
            swap_chain_desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
            swap_chain_desc.AlphaMode = DXGI_ALPHA_MODE_UNSPECIFIED;
            swap_chain_desc.Flags = 0;

            Microsoft::WRL::ComPtr<IDXGISwapChain1> swap_chain;
            target->guarded_swap_chain_create_attempted = true;
            hr = factory->CreateSwapChainForHwnd(
                target->command_queue.Get(),
                static_cast<HWND>(native_window_handle),
                &swap_chain_desc,
                nullptr,
                nullptr,
                &swap_chain
            );
            target->guarded_swap_chain_create_hr = hr;

            if (SUCCEEDED(hr)) {
                hr = swap_chain.As(&target->guarded_swap_chain);
                target->guarded_swap_chain_query_hr = hr;
                target->guarded_swap_chain_created = SUCCEEDED(hr);
                target->swap_chain_ready = target->guarded_swap_chain_created;
            }
        }
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_swap_chain_creation_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"native_window_handle_ready":)";
    payload += target->guarded_swap_chain_native_window_handle_ready ? "true" : "false";
    payload += R"(,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"prerequisites_ready":)";
    payload += prerequisites_ready ? "true" : "false";
    payload += R"(,"swap_chain_create_attempted":)";
    payload += target->guarded_swap_chain_create_attempted ? "true" : "false";
    payload += R"(,"swap_chain_created":)";
    payload += target->guarded_swap_chain_created ? "true" : "false";
    payload += R"(,"swap_chain_ready":)";
    payload += target->swap_chain_ready ? "true" : "false";
    payload += R"(,"swap_chain_desc":{"buffer_count":2,)"
               R"("format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
               R"("swap_effect":"DXGI_SWAP_EFFECT_FLIP_DISCARD",)"
               R"("sample_count":1,"usage":"DXGI_USAGE_RENDER_TARGET_OUTPUT"},)"
               R"("back_buffers_acquired":false,"render_target_views_created":false,)"
               R"("present_called":false,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"factory_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_factory_hr);
    payload += R"(","swap_chain_create_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_create_hr);
    payload += R"(","swap_chain_query_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_query_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_back_buffer_rtv_diagnostics_json(void* context) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_back_buffer_rtv_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"swap_chain_created":false,"rtv_heap_ready":false,"back_buffer_get_attempted":false,"back_buffers_acquired":false,"render_target_views_created":false,"render_target_bound":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool prerequisites_ready =
        target->device != nullptr &&
        target->guarded_swap_chain != nullptr &&
        target->rtv_heap != nullptr;
    bool back_buffer_get_attempted = false;

    if (prerequisites_ready && !target->guarded_back_buffers_acquired) {
        back_buffer_get_attempted = true;
        HRESULT hr = target->guarded_swap_chain->GetBuffer(
            0,
            IID_PPV_ARGS(&target->guarded_back_buffer_0)
        );
        target->guarded_back_buffer_0_hr = hr;

        if (SUCCEEDED(hr)) {
            hr = target->guarded_swap_chain->GetBuffer(
                1,
                IID_PPV_ARGS(&target->guarded_back_buffer_1)
            );
            target->guarded_back_buffer_1_hr = hr;
        }

        target->guarded_back_buffers_acquired =
            target->guarded_back_buffer_0 != nullptr &&
            target->guarded_back_buffer_1 != nullptr;

        if (target->guarded_back_buffers_acquired) {
            D3D12_CPU_DESCRIPTOR_HANDLE rtv_handle = target->rtv_heap->GetCPUDescriptorHandleForHeapStart();
            const UINT rtv_increment = target->device->GetDescriptorHandleIncrementSize(
                D3D12_DESCRIPTOR_HEAP_TYPE_RTV
            );
            target->device->CreateRenderTargetView(target->guarded_back_buffer_0.Get(), nullptr, rtv_handle);
            rtv_handle.ptr += rtv_increment;
            target->device->CreateRenderTargetView(target->guarded_back_buffer_1.Get(), nullptr, rtv_handle);
            target->guarded_render_target_views_created = true;
            target->render_target_metadata_ready = true;
        }
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_back_buffer_rtv_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"swap_chain_created":)";
    payload += target->guarded_swap_chain_created ? "true" : "false";
    payload += R"(,"rtv_heap_ready":)";
    payload += target->rtv_heap ? "true" : "false";
    payload += R"(,"prerequisites_ready":)";
    payload += prerequisites_ready ? "true" : "false";
    payload += R"(,"back_buffer_get_attempted":)";
    payload += back_buffer_get_attempted ? "true" : "false";
    payload += R"(,"expected_back_buffer_count":2,"back_buffers_acquired":)";
    payload += target->guarded_back_buffers_acquired ? "true" : "false";
    payload += R"(,"render_target_views_created":)";
    payload += target->guarded_render_target_views_created ? "true" : "false";
    payload += R"(,"render_target_bound":false,"resource_barriers_recorded":false,)"
               R"("clear_recorded":false,"present_called":false,"present_enabled":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"back_buffer_0_hresult":")";
    payload += hresult_hex(target->guarded_back_buffer_0_hr);
    payload += R"(","back_buffer_1_hresult":")";
    payload += hresult_hex(target->guarded_back_buffer_1_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_barrier_clear_recording_diagnostics_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_barrier_clear_recording_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_command_allocator":false,"retained_command_list":false,"back_buffers_acquired":false,"render_target_views_created":false,"barrier_clear_recording_attempted":false,"resource_barriers_recorded":false,"clear_recorded":false,"command_list_closed":false,"command_list_executed":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool prerequisites_ready =
        target->command_allocator != nullptr &&
        target->command_list != nullptr &&
        target->guarded_back_buffer_0 != nullptr &&
        target->rtv_heap != nullptr &&
        target->guarded_render_target_views_created;

    if (prerequisites_ready && !target->guarded_barrier_clear_command_list_closed) {
        target->guarded_barrier_clear_attempted = true;
        HRESULT hr = target->command_allocator->Reset();
        target->guarded_barrier_clear_allocator_reset_hr = hr;

        if (SUCCEEDED(hr)) {
            hr = target->command_list->Reset(target->command_allocator.Get(), nullptr);
            target->guarded_barrier_clear_command_list_reset_hr = hr;
        }

        if (SUCCEEDED(hr)) {
            D3D12_RESOURCE_BARRIER barrier{};
            barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            barrier.Flags = D3D12_RESOURCE_BARRIER_FLAG_NONE;
            barrier.Transition.pResource = target->guarded_back_buffer_0.Get();
            barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
            barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT;
            barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_RENDER_TARGET;
            target->command_list->ResourceBarrier(1, &barrier);
            target->guarded_resource_barriers_recorded = true;

            D3D12_CPU_DESCRIPTOR_HANDLE rtv_handle = target->rtv_heap->GetCPUDescriptorHandleForHeapStart();
            constexpr FLOAT clear_color[4] = { 0.0f, 0.0f, 0.0f, 1.0f };
            target->command_list->ClearRenderTargetView(rtv_handle, clear_color, 0, nullptr);
            target->guarded_clear_recorded = true;

            barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
            barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PRESENT;
            target->command_list->ResourceBarrier(1, &barrier);
        }

        if (target->guarded_resource_barriers_recorded && target->guarded_clear_recorded) {
            hr = target->command_list->Close();
            target->guarded_barrier_clear_command_list_close_hr = hr;
            target->guarded_barrier_clear_command_list_closed = SUCCEEDED(hr);
            target->barrier_clear_pass_metadata_ready = target->guarded_barrier_clear_command_list_closed;
        }
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_barrier_clear_recording_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_command_allocator":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"retained_command_list":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"back_buffers_acquired":)";
    payload += target->guarded_back_buffers_acquired ? "true" : "false";
    payload += R"(,"render_target_views_created":)";
    payload += target->guarded_render_target_views_created ? "true" : "false";
    payload += R"(,"prerequisites_ready":)";
    payload += prerequisites_ready ? "true" : "false";
    payload += R"(,"barrier_clear_recording_attempted":)";
    payload += target->guarded_barrier_clear_attempted ? "true" : "false";
    payload += R"(,"resource_barriers_recorded":)";
    payload += target->guarded_resource_barriers_recorded ? "true" : "false";
    payload += R"(,"clear_recorded":)";
    payload += target->guarded_clear_recorded ? "true" : "false";
    payload += R"(,"clear_color":[0.0,0.0,0.0,1.0],"command_list_closed":)";
    payload += target->guarded_barrier_clear_command_list_closed ? "true" : "false";
    payload += R"(,"command_list_executed":false,"present_called":false,)"
               R"("present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"allocator_reset_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_allocator_reset_hr);
    payload += R"(","command_list_reset_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_command_list_reset_hr);
    payload += R"(","command_list_close_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_command_list_close_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"retained_command_queue":false,"recorded_clear_pass_ready":false,"clear_pass_command_list_executed":false,"command_lists_submitted":0,"draw_calls_recorded":0,"fence_created":false,"fence_signaled":false,"fence_completed":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool recorded_clear_pass_ready =
        target->command_queue != nullptr &&
        target->command_list != nullptr &&
        target->guarded_barrier_clear_command_list_closed &&
        target->guarded_resource_barriers_recorded &&
        target->guarded_clear_recorded;

    if (recorded_clear_pass_ready && !target->guarded_clear_pass_fence_completed) {
        ID3D12CommandList* command_lists[] = { target->command_list.Get() };
        target->command_queue->ExecuteCommandLists(1, command_lists);
        target->guarded_clear_pass_command_list_executed = true;

        HRESULT hr = target->device
            ? target->device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&target->guarded_clear_pass_fence))
            : E_FAIL;
        target->guarded_clear_pass_fence_hr = hr;
        target->guarded_clear_pass_fence_ready = SUCCEEDED(hr);

        if (target->guarded_clear_pass_fence_ready) {
            hr = target->command_queue->Signal(
                target->guarded_clear_pass_fence.Get(),
                target->guarded_clear_pass_fence_value
            );
            target->guarded_clear_pass_signal_hr = hr;
            target->guarded_clear_pass_fence_signaled = SUCCEEDED(hr);
        }

        if (
            target->guarded_clear_pass_fence_signaled &&
            target->guarded_clear_pass_fence->GetCompletedValue() < target->guarded_clear_pass_fence_value
        ) {
            HANDLE fence_event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
            if (fence_event != nullptr) {
                hr = target->guarded_clear_pass_fence->SetEventOnCompletion(
                    target->guarded_clear_pass_fence_value,
                    fence_event
                );
                target->guarded_clear_pass_set_event_hr = hr;
                if (SUCCEEDED(hr)) {
                    target->guarded_clear_pass_wait_result = WaitForSingleObject(fence_event, 2000);
                    target->guarded_clear_pass_fence_waited =
                        target->guarded_clear_pass_wait_result == WAIT_OBJECT_0;
                }
                CloseHandle(fence_event);
            } else {
                target->guarded_clear_pass_set_event_hr = HRESULT_FROM_WIN32(GetLastError());
            }
        } else if (target->guarded_clear_pass_fence_signaled) {
            target->guarded_clear_pass_set_event_hr = S_OK;
            target->guarded_clear_pass_wait_result = WAIT_OBJECT_0;
        }

        target->guarded_clear_pass_fence_completed =
            target->guarded_clear_pass_fence_signaled &&
            target->guarded_clear_pass_fence->GetCompletedValue() >= target->guarded_clear_pass_fence_value;
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"recorded_clear_pass_ready":)";
    payload += recorded_clear_pass_ready ? "true" : "false";
    payload += R"(,"resource_barriers_recorded":)";
    payload += target->guarded_resource_barriers_recorded ? "true" : "false";
    payload += R"(,"clear_recorded":)";
    payload += target->guarded_clear_recorded ? "true" : "false";
    payload += R"(,"clear_pass_command_list_executed":)";
    payload += target->guarded_clear_pass_command_list_executed ? "true" : "false";
    payload += R"(,"command_lists_submitted":)";
    payload += target->guarded_clear_pass_command_list_executed ? "1" : "0";
    payload += R"(,"draw_calls_recorded":0,"fence_created":)";
    payload += target->guarded_clear_pass_fence_ready ? "true" : "false";
    payload += R"(,"fence_signaled":)";
    payload += target->guarded_clear_pass_fence_signaled ? "true" : "false";
    payload += R"(,"fence_completed":)";
    payload += target->guarded_clear_pass_fence_completed ? "true" : "false";
    payload += R"(,"fence_waited":)";
    payload += target->guarded_clear_pass_fence_waited ? "true" : "false";
    payload += R"(,"present_called":false,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"wait_result":)";
    payload += std::to_string(static_cast<unsigned long>(target->guarded_clear_pass_wait_result));
    payload += R"(,"fence_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_fence_hr);
    payload += R"(","signal_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_signal_hr);
    payload += R"(","set_event_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_set_event_hr);
    payload += R"(","phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_post_clear_present_readiness_diagnostics_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_post_clear_present_readiness_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"swap_chain_created":false,"back_buffers_acquired":false,"render_target_views_created":false,"clear_pass_executed":false,"clear_pass_fence_completed":false,"present_ready":false,"present_called":false,"present_enabled":false,"draw_submission_enabled":false})";
    }

    const bool clear_pass_executed = target->guarded_clear_pass_command_list_executed;
    const bool clear_pass_fence_completed = target->guarded_clear_pass_fence_completed;
    const bool present_ready =
        target->guarded_swap_chain_created &&
        target->guarded_back_buffers_acquired &&
        target->guarded_render_target_views_created &&
        clear_pass_executed &&
        clear_pass_fence_completed;
    target->post_clear_present_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_post_clear_present_readiness_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"swap_chain_created":)";
    payload += target->guarded_swap_chain_created ? "true" : "false";
    payload += R"(,"back_buffers_acquired":)";
    payload += target->guarded_back_buffers_acquired ? "true" : "false";
    payload += R"(,"render_target_views_created":)";
    payload += target->guarded_render_target_views_created ? "true" : "false";
    payload += R"(,"resource_barriers_recorded":)";
    payload += target->guarded_resource_barriers_recorded ? "true" : "false";
    payload += R"(,"clear_recorded":)";
    payload += target->guarded_clear_recorded ? "true" : "false";
    payload += R"(,"clear_pass_executed":)";
    payload += clear_pass_executed ? "true" : "false";
    payload += R"(,"clear_pass_fence_completed":)";
    payload += clear_pass_fence_completed ? "true" : "false";
    payload += R"(,"back_buffer_state_expected":"D3D12_RESOURCE_STATE_PRESENT",)"
               R"("present_ready":)";
    payload += present_ready ? "true" : "false";
    payload += R"(,"present_called":false,"present_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["swap_chain_missing","back_buffers_missing",)"
               R"("rtv_missing","clear_pass_not_executed","clear_pass_fence_incomplete",)"
               R"("present_call_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_present_call_diagnostics_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_present_call_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"swap_chain_created":false,"back_buffers_acquired":false,"clear_pass_executed":false,"clear_pass_fence_completed":false,"present_ready":false,"present_called":false,"present_succeeded":false,"draw_calls_recorded":0,"draw_submission_enabled":false})";
    }

    const bool present_ready =
        target->guarded_swap_chain_created &&
        target->guarded_back_buffers_acquired &&
        target->guarded_render_target_views_created &&
        target->guarded_clear_pass_command_list_executed &&
        target->guarded_clear_pass_fence_completed &&
        target->guarded_swap_chain != nullptr;
    target->guarded_present_ready = present_ready;

    if (present_ready && !target->guarded_present_called) {
        target->guarded_present_hr = target->guarded_swap_chain->Present(0, 0);
        target->guarded_present_called = true;
        target->guarded_present_succeeded = SUCCEEDED(target->guarded_present_hr);
    }

    payload =
        R"({"schema":"renderer_d3d12_guarded_present_call_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"swap_chain_created":)";
    payload += target->guarded_swap_chain_created ? "true" : "false";
    payload += R"(,"back_buffers_acquired":)";
    payload += target->guarded_back_buffers_acquired ? "true" : "false";
    payload += R"(,"render_target_views_created":)";
    payload += target->guarded_render_target_views_created ? "true" : "false";
    payload += R"(,"clear_pass_executed":)";
    payload += target->guarded_clear_pass_command_list_executed ? "true" : "false";
    payload += R"(,"clear_pass_fence_completed":)";
    payload += target->guarded_clear_pass_fence_completed ? "true" : "false";
    payload += R"(,"present_ready":)";
    payload += target->guarded_present_ready ? "true" : "false";
    payload += R"(,"present_called":)";
    payload += target->guarded_present_called ? "true" : "false";
    payload += R"(,"present_succeeded":)";
    payload += target->guarded_present_succeeded ? "true" : "false";
    payload += R"(,"present_sync_interval":0,"present_flags":0,"draw_calls_recorded":0,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"present_hresult":")";
    payload += hresult_hex(target->guarded_present_hr);
    payload += R"(","failure_points":["swap_chain_missing","back_buffers_missing",)"
               R"("rtv_missing","clear_pass_not_executed","clear_pass_fence_incomplete",)"
               R"("present_failed"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_post_present_frame_accounting_diagnostics_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_post_present_frame_accounting_diagnostics.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"present_called":false,"present_succeeded":false,"frame_presented":false,"frame_index":0,"presented_frame_count":0,"draw_calls_recorded":0,"draw_submission_enabled":false})";
    }

    const bool frame_presented = target->guarded_present_called && target->guarded_present_succeeded;
    target->post_present_frame_accounting_ready = true;
    target->diagnostic_presented_frame_count = frame_presented ? 1 : 0;
    target->diagnostic_frame_index = frame_presented ? target->diagnostic_presented_frame_count : 0;

    payload =
        R"({"schema":"renderer_d3d12_post_present_frame_accounting_diagnostics.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"present_ready":)";
    payload += target->guarded_present_ready ? "true" : "false";
    payload += R"(,"present_called":)";
    payload += target->guarded_present_called ? "true" : "false";
    payload += R"(,"present_succeeded":)";
    payload += target->guarded_present_succeeded ? "true" : "false";
    payload += R"(,"frame_presented":)";
    payload += frame_presented ? "true" : "false";
    payload += R"(,"frame_index":)";
    payload += std::to_string(static_cast<unsigned long long>(target->diagnostic_frame_index));
    payload += R"(,"presented_frame_count":)";
    payload += std::to_string(static_cast<unsigned long long>(target->diagnostic_presented_frame_count));
    payload += R"(,"cpu_submit_ms":0.0,"gpu_frame_ms":0.0,"draw_calls_recorded":0,)"
               R"("triangles_submitted":0,"resource_uploads":0,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["present_not_called","present_failed",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_draw_list_readiness_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_draw_list_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"draw_list_ready":false,"mesh_handle_count":0,"material_handle_count":0,"draw_command_count":0,"draw_calls_recorded":0,"triangles_submitted":0,"draw_submission_enabled":false})";
    }

    target->draw_list_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_draw_list_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"renderer_contract_ready":true,"draw_list_ready":false,)"
               R"("draw_list_source":"future_native_payload",)"
               R"("requires_mesh_handles":true,"requires_material_handles":true,)"
               R"("requires_transform_packets":true,"requires_resource_residency":true,)"
               R"("mesh_handle_count":0,"material_handle_count":0,)"
               R"("transform_packet_count":0,"resource_residency_packet_count":0,)"
               R"("draw_command_count":0,"indexed_draw_command_count":0,)"
               R"("instanced_draw_command_count":0,"skinned_draw_command_count":0,)"
               R"("draw_calls_recorded":0,"triangles_submitted":0,)"
               R"("resource_uploads":0,"command_list_recorded_for_draws":false,)"
               R"("command_list_executed_for_draws":false,"present_after_draws_enabled":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["draw_list_missing","mesh_handles_missing",)"
               R"("material_handles_missing","transform_packets_missing",)"
               R"("resource_residency_missing","draw_submission_disabled"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_resource_binding_readiness_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_resource_binding_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"resource_binding_ready":false,"descriptor_tables_bound":false,"vertex_buffers_bound":0,"index_buffers_bound":0,"constant_buffers_bound":0,"shader_resources_bound":0,"draw_submission_enabled":false})";
    }

    target->resource_binding_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_resource_binding_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"cbv_srv_uav_heap_ready":)";
    payload += target->cbv_srv_uav_heap ? "true" : "false";
    payload += R"(,"rtv_heap_ready":)";
    payload += target->rtv_heap ? "true" : "false";
    payload += R"(,"dsv_heap_ready":)";
    payload += target->dsv_heap ? "true" : "false";
    payload += R"(,"draw_list_ready":false,"resource_binding_ready":false,)"
               R"("root_signature_created":false,"pipeline_state_created":false,)"
               R"("descriptor_heaps_set_for_draws":false,"descriptor_tables_bound":false,)"
               R"("vertex_buffers_bound":0,"index_buffers_bound":0,)"
               R"("constant_buffers_bound":0,"shader_resources_bound":0,)"
               R"("samplers_bound":0,"textures_bound":0,"skin_palettes_bound":0,)"
               R"("materials_bound":0,"resource_barriers_for_draws_recorded":false,)"
               R"("command_list_recorded_for_draws":false,"draw_calls_recorded":0,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["draw_list_missing","root_signature_missing",)"
               R"("pipeline_state_missing","descriptor_tables_missing",)"
               R"("vertex_buffers_missing","index_buffers_missing",)"
               R"("shader_resources_missing","draw_submission_disabled"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_pipeline_state_readiness_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_pipeline_state_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"pipeline_state_ready":false,"root_signature_created":false,"pipeline_state_created":false,"vertex_shader_ready":false,"pixel_shader_ready":false,"draw_submission_enabled":false})";
    }

    target->pipeline_state_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_pipeline_state_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"resource_binding_ready":false,"pipeline_state_ready":false,)"
               R"("root_signature_created":false,"root_parameters_declared":0,)"
               R"("descriptor_ranges_declared":0,"static_samplers_declared":0,)"
               R"("pipeline_state_created":false,"input_layout_ready":false,)"
               R"("input_layout_semantics":["POSITION","NORMAL","TEXCOORD","BLENDINDICES","BLENDWEIGHT"],)"
               R"("vertex_shader_ready":false,"pixel_shader_ready":false,)"
               R"("skinning_shader_variant_ready":false,"sprite_shader_variant_ready":false,)"
               R"("depth_stencil_state_ready":false,"rasterizer_state_ready":false,)"
               R"("blend_state_ready":false,"render_target_format":"DXGI_FORMAT_R8G8B8A8_UNORM",)"
               R"("depth_stencil_format":"DXGI_FORMAT_D24_UNORM_S8_UINT",)"
               R"("primitive_topology_type":"D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE",)"
               R"("command_list_recorded_for_draws":false,"draw_calls_recorded":0,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["root_signature_missing","pipeline_state_missing",)"
               R"("vertex_shader_missing","pixel_shader_missing","input_layout_missing",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_shader_bytecode_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_shader_bytecode_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"shader_bytecode_ready":false,"vertex_shader_compiled":false,"pixel_shader_compiled":false,"compiled_shader_blob_count":0,"draw_submission_enabled":false})";
    }

    target->guarded_shader_bytecode_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_shader_bytecode_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"pipeline_state_ready":false,"shader_bytecode_ready":false,)"
               R"("shader_compiler_invoked":false,"dxc_compiler_required":true,)"
               R"("legacy_d3dcompile_used":false,"compiled_shader_blob_count":0,)"
               R"("vertex_shader_entry":"VSMain","vertex_shader_target":"vs_6_0",)"
               R"("pixel_shader_entry":"PSMain","pixel_shader_target":"ps_6_0",)"
               R"("vertex_shader_compiled":false,"pixel_shader_compiled":false,)"
               R"("skinning_shader_variant_compiled":false,)"
               R"("sprite_shader_variant_compiled":false,)"
               R"("debug_shader_symbols_embedded":false,)"
               R"("shader_reflection_ready":false,"input_layout_from_reflection":false,)"
               R"("root_signature_from_shader":false,"pipeline_state_created":false,)"
               R"("draw_calls_recorded":0,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["shader_sources_missing","dxc_compiler_missing",)"
               R"("vertex_shader_missing","pixel_shader_missing",)"
               R"("shader_reflection_missing","draw_submission_disabled"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_shader_reflection_input_layout_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_shader_reflection_input_layout_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"shader_reflection_ready":false,"input_layout_ready":false,"input_element_count":0,"draw_submission_enabled":false})";
    }

    target->shader_reflection_input_layout_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_shader_reflection_input_layout_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"shader_bytecode_ready":false,"shader_reflection_ready":false,)"
               R"("reflection_api":"DXC reflection","reflection_invoked":false,)"
               R"("input_layout_ready":false,"input_layout_from_reflection":false,)"
               R"("input_element_count":0,"required_input_elements":[)"
               R"({"semantic":"POSITION","format":"DXGI_FORMAT_R32G32B32_FLOAT","slot":0},)"
               R"({"semantic":"NORMAL","format":"DXGI_FORMAT_R32G32B32_FLOAT","slot":0},)"
               R"({"semantic":"TEXCOORD","format":"DXGI_FORMAT_R32G32_FLOAT","slot":0},)"
               R"({"semantic":"BLENDINDICES","format":"DXGI_FORMAT_R32G32B32A32_UINT","slot":0},)"
               R"({"semantic":"BLENDWEIGHT","format":"DXGI_FORMAT_R32G32B32A32_FLOAT","slot":0}],)"
               R"("actual_input_elements":[],)"
               R"("vertex_stride_bytes":0,"skinned_vertex_stride_bytes":0,)"
               R"("instance_data_supported":false,"sprite_vertex_layout_supported":false,)"
               R"("root_signature_from_reflection":false,"pipeline_state_created":false,)"
               R"("draw_calls_recorded":0,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["shader_bytecode_missing","reflection_not_invoked",)"
               R"("input_layout_missing","vertex_stride_missing",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_root_signature_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_root_signature_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"root_signature_ready":false,"root_signature_created":false,"root_parameter_count":0,"descriptor_range_count":0,"draw_submission_enabled":false})";
    }

    target->guarded_root_signature_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_root_signature_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"shader_reflection_ready":false,"root_signature_ready":false,)"
               R"("root_signature_serialized":false,"root_signature_created":false,)"
               R"("root_signature_version":"D3D_ROOT_SIGNATURE_VERSION_1_1",)"
               R"("root_parameter_count":0,"descriptor_range_count":0,)"
               R"("static_sampler_count":0,"expected_root_parameters":[)"
               R"({"slot":"frame_constants","type":"CBV","register":"b0","space":0},)"
               R"({"slot":"object_constants","type":"CBV","register":"b1","space":0},)"
               R"({"slot":"material_constants","type":"CBV","register":"b2","space":0},)"
               R"({"slot":"texture_table","type":"SRV_TABLE","register":"t0","space":0},)"
               R"({"slot":"skin_palette","type":"SRV","register":"t8","space":0}],)"
               R"("expected_static_samplers":[{"slot":"linear_wrap","register":"s0","space":0}],)"
               R"("actual_root_parameters":[],"actual_descriptor_ranges":[],)"
               R"("descriptor_tables_ready":false,"root_constants_ready":false,)"
               R"("root_signature_from_reflection":false,"pipeline_state_created":false,)"
               R"("draw_calls_recorded":0,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["shader_reflection_missing",)"
               R"("root_signature_not_serialized","root_signature_missing",)"
               R"("descriptor_ranges_missing","static_samplers_missing",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_pipeline_state_object_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_pipeline_state_object_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"pipeline_state_ready":false,"pipeline_state_created":false,"pso_descriptor_ready":false,"draw_submission_enabled":false})";
    }

    target->guarded_pipeline_state_object_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_pipeline_state_object_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"root_signature_ready":false,"shader_bytecode_ready":false,)"
               R"("input_layout_ready":false,"pipeline_state_ready":false,)"
               R"("pso_descriptor_ready":false,"pipeline_state_created":false,)"
               R"("graphics_pso_desc_fields":[)"
               R"({"field":"pRootSignature","ready":false},)"
               R"({"field":"VS","ready":false,"entry":"VSMain","target":"vs_6_0"},)"
               R"({"field":"PS","ready":false,"entry":"PSMain","target":"ps_6_0"},)"
               R"({"field":"InputLayout","ready":false,"element_count":0},)"
               R"({"field":"BlendState","ready":false},)"
               R"({"field":"RasterizerState","ready":false},)"
               R"({"field":"DepthStencilState","ready":false},)"
               R"({"field":"SampleMask","ready":false},)"
               R"({"field":"PrimitiveTopologyType","ready":false},)"
               R"({"field":"RTVFormats","ready":false,"format":"DXGI_FORMAT_R8G8B8A8_UNORM"},)"
               R"({"field":"DSVFormat","ready":false,"format":"DXGI_FORMAT_D24_UNORM_S8_UINT"},)"
               R"({"field":"SampleDesc","ready":false,"count":1}],)"
               R"("blend_state_ready":false,"rasterizer_state_ready":false,)"
               R"("depth_stencil_state_ready":false,"sample_mask_ready":false,)"
               R"("primitive_topology_ready":false,"rtv_formats_ready":false,)"
               R"("dsv_format_ready":false,"sample_desc_ready":false,)"
               R"("cached_pso_count":0,"draw_calls_recorded":0,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["root_signature_missing",)"
               R"("shader_bytecode_missing","input_layout_missing",)"
               R"("pso_descriptor_incomplete","pipeline_state_missing",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_draw_command_recording_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_draw_command_recording_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"command_list_recorded_for_draws":false,"draw_command_count":0,"draw_submission_enabled":false})";
    }

    target->guarded_draw_command_recording_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_draw_command_recording_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"draw_list_ready":false,"resource_binding_ready":false,)"
               R"("root_signature_ready":false,"pipeline_state_ready":false,)"
               R"("vertex_buffers_ready":false,"index_buffers_ready":false,)"
               R"("constant_buffers_ready":false,"descriptor_tables_ready":false,)"
               R"("command_allocator_ready":)";
    payload += target->command_allocator ? "true" : "false";
    payload += R"(,"command_list_ready":)";
    payload += target->command_list ? "true" : "false";
    payload += R"(,"command_list_reset_for_draws":false,)"
               R"("command_list_recorded_for_draws":false,)"
               R"("command_list_closed_for_draws":false,)"
               R"("render_targets_bound_for_draws":false,)"
               R"("viewport_bound":false,"scissor_bound":false,)"
               R"("primitive_topology_bound":false,)"
               R"("draw_command_count":0,"indexed_draw_command_count":0,)"
               R"("instanced_draw_command_count":0,"skinned_draw_command_count":0,)"
               R"("sprite_draw_command_count":0,"submitted_vertex_count":0,)"
               R"("submitted_index_count":0,"submitted_instance_count":0,)"
               R"("draw_packets":[],"resource_barriers_for_draws_recorded":false,)"
               R"("present_after_draws_enabled":false,"draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["draw_list_missing","resource_bindings_missing",)"
               R"("root_signature_missing","pipeline_state_missing",)"
               R"("vertex_buffers_missing","index_buffers_missing",)"
               R"("descriptor_tables_missing","render_targets_missing",)"
               R"("draw_commands_not_recorded","draw_submission_disabled"],)"
               R"("phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_draw_submission_readiness_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_draw_submission_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"draw_submission_ready":false,"draw_submission_attempted":false,"command_lists_submitted_for_draws":0,"draw_submission_enabled":false})";
    }

    target->guarded_draw_submission_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_draw_submission_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"retained_command_queue":)";
    payload += target->command_queue ? "true" : "false";
    payload += R"(,"draw_command_recording_ready":false,)"
               R"("draw_command_list_closed":false,)"
               R"("draw_submission_ready":false,)"
               R"("draw_submission_attempted":false,)"
               R"("command_lists_submitted_for_draws":0,)"
               R"("draw_fence_created":false,"draw_fence_signaled":false,)"
               R"("draw_fence_completed":false,"draw_fence_waited":false,)"
               R"("gpu_timeline_value":0,"cpu_wait_milliseconds":0,)"
               R"("submitted_draw_call_count":0,"submitted_triangle_count":0,)"
               R"("submitted_instance_count":0,"submitted_resource_barrier_count":0,)"
               R"("present_after_draws_ready":false,)"
               R"("present_after_draws_called":false,)"
               R"("present_after_draws_succeeded":false,)"
               R"("frame_accounting_after_draws_ready":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["draw_command_list_missing",)"
               R"("draw_command_list_not_closed","draw_commands_missing",)"
               R"("draw_fence_missing","draw_submission_disabled",)"
               R"("present_after_draws_disabled"],"phase":"P1 diagnostic boundary"})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata_json(
    void* context
) {
    static thread_local std::string payload;
    auto* target = context_from_handle(context);
    if (target == nullptr) {
        return R"({"schema":"renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata.v1","backend_id":"renderer_d3d12","status":"null_context","diagnostic_only":true,"post_draw_frame_accounting_ready":false,"frame_presented_after_draws":false,"draw_submission_enabled":false})";
    }

    target->guarded_post_draw_frame_accounting_readiness_metadata_ready = true;

    payload =
        R"({"schema":"renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata.v1",)"
        R"("backend_id":"renderer_d3d12","diagnostic_only":true,"retained_device":)";
    payload += target->device ? "true" : "false";
    payload += R"(,"draw_submission_ready":false,)"
               R"("draw_submission_attempted":false,)"
               R"("draw_submission_completed":false,)"
               R"("draw_fence_completed":false,)"
               R"("present_after_draws_ready":false,)"
               R"("present_after_draws_called":false,)"
               R"("present_after_draws_succeeded":false,)"
               R"("frame_presented_after_draws":false,)"
               R"("post_draw_frame_accounting_ready":false,)"
               R"("post_draw_frame_accounting_recorded":false,)"
               R"("diagnostic_frame_index_after_draws":0,)"
               R"("presented_frame_count_after_draws":0,)"
               R"("submitted_draw_call_count":0,)"
               R"("submitted_triangle_count":0,)"
               R"("submitted_instance_count":0,)"
               R"("submitted_vertex_count":0,)"
               R"("submitted_index_count":0,)"
               R"("resource_upload_count_after_draws":0,)"
               R"("resource_barrier_count_after_draws":0,)"
               R"("cpu_frame_time_microseconds":0,)"
               R"("gpu_frame_time_microseconds":0,)"
               R"("gpu_timeline_value_after_draws":0,)"
               R"("frame_statistics_export_ready":false,)"
               R"("draw_submission_enabled":)";
    payload += target->draw_submission_enabled ? "true" : "false";
    payload += R"(,"failure_points":["draw_submission_missing",)"
               R"("draw_fence_incomplete","present_after_draws_missing",)"
               R"("post_draw_accounting_not_recorded",)"
               R"("draw_submission_disabled"],"phase":"P1 diagnostic boundary"})";
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
        R"("command_recording_dry_run","guarded_command_recording",)"
        R"("no_draw_execution_fence","present_readiness_metadata",)"
        R"("guarded_swap_chain_creation","guarded_back_buffer_rtv",)"
        R"("guarded_barrier_clear_recording","guarded_clear_pass_execution_fence",)"
        R"("post_clear_present_readiness","guarded_present_call",)"
        R"("post_present_frame_accounting","draw_list_readiness_metadata",)"
        R"("resource_binding_readiness_metadata","pipeline_state_readiness_metadata",)"
        R"("guarded_shader_bytecode_metadata","shader_reflection_input_layout_metadata",)"
        R"("guarded_root_signature_metadata","guarded_pipeline_state_object_metadata",)"
        R"("guarded_draw_command_recording_metadata",)"
        R"("guarded_draw_submission_readiness_metadata",)"
        R"("guarded_post_draw_frame_accounting_readiness_metadata"],)"
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
    payload += R"(,"guarded_allocator_reset":)";
    payload += target->guarded_allocator_reset ? "true" : "false";
    payload += R"(,"guarded_command_list_reset":)";
    payload += target->guarded_command_list_reset ? "true" : "false";
    payload += R"(,"guarded_command_list_closed":)";
    payload += target->guarded_command_list_closed ? "true" : "false";
    payload += R"(,"no_draw_command_list_executed":)";
    payload += target->no_draw_command_list_executed ? "true" : "false";
    payload += R"(,"no_draw_fence_completed":)";
    payload += target->no_draw_fence_completed ? "true" : "false";
    payload += R"(,"present_readiness_metadata_ready":)";
    payload += target->present_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_swap_chain_created":)";
    payload += target->guarded_swap_chain_created ? "true" : "false";
    payload += R"(,"guarded_back_buffers_acquired":)";
    payload += target->guarded_back_buffers_acquired ? "true" : "false";
    payload += R"(,"guarded_render_target_views_created":)";
    payload += target->guarded_render_target_views_created ? "true" : "false";
    payload += R"(,"guarded_resource_barriers_recorded":)";
    payload += target->guarded_resource_barriers_recorded ? "true" : "false";
    payload += R"(,"guarded_clear_recorded":)";
    payload += target->guarded_clear_recorded ? "true" : "false";
    payload += R"(,"guarded_clear_pass_command_list_executed":)";
    payload += target->guarded_clear_pass_command_list_executed ? "true" : "false";
    payload += R"(,"guarded_clear_pass_fence_completed":)";
    payload += target->guarded_clear_pass_fence_completed ? "true" : "false";
    payload += R"(,"post_clear_present_readiness_metadata_ready":)";
    payload += target->post_clear_present_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_present_ready":)";
    payload += target->guarded_present_ready ? "true" : "false";
    payload += R"(,"guarded_present_called":)";
    payload += target->guarded_present_called ? "true" : "false";
    payload += R"(,"guarded_present_succeeded":)";
    payload += target->guarded_present_succeeded ? "true" : "false";
    payload += R"(,"post_present_frame_accounting_ready":)";
    payload += target->post_present_frame_accounting_ready ? "true" : "false";
    payload += R"(,"draw_list_readiness_metadata_ready":)";
    payload += target->draw_list_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"resource_binding_readiness_metadata_ready":)";
    payload += target->resource_binding_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"pipeline_state_readiness_metadata_ready":)";
    payload += target->pipeline_state_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_shader_bytecode_metadata_ready":)";
    payload += target->guarded_shader_bytecode_metadata_ready ? "true" : "false";
    payload += R"(,"shader_reflection_input_layout_metadata_ready":)";
    payload += target->shader_reflection_input_layout_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_root_signature_metadata_ready":)";
    payload += target->guarded_root_signature_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_pipeline_state_object_metadata_ready":)";
    payload += target->guarded_pipeline_state_object_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_draw_command_recording_metadata_ready":)";
    payload += target->guarded_draw_command_recording_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_draw_submission_readiness_metadata_ready":)";
    payload += target->guarded_draw_submission_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"guarded_post_draw_frame_accounting_readiness_metadata_ready":)";
    payload += target->guarded_post_draw_frame_accounting_readiness_metadata_ready ? "true" : "false";
    payload += R"(,"diagnostic_frame_index":)";
    payload += std::to_string(static_cast<unsigned long long>(target->diagnostic_frame_index));
    payload += R"(,"diagnostic_presented_frame_count":)";
    payload += std::to_string(static_cast<unsigned long long>(target->diagnostic_presented_frame_count));
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
    payload += R"(","guarded_allocator_reset_hresult":")";
    payload += hresult_hex(target->guarded_allocator_reset_hr);
    payload += R"(","guarded_command_list_reset_hresult":")";
    payload += hresult_hex(target->guarded_command_list_reset_hr);
    payload += R"(","guarded_command_list_close_hresult":")";
    payload += hresult_hex(target->guarded_command_list_close_hr);
    payload += R"(","no_draw_fence_hresult":")";
    payload += hresult_hex(target->no_draw_fence_hr);
    payload += R"(","no_draw_signal_hresult":")";
    payload += hresult_hex(target->no_draw_signal_hr);
    payload += R"(","no_draw_set_event_hresult":")";
    payload += hresult_hex(target->no_draw_set_event_hr);
    payload += R"(","guarded_swap_chain_factory_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_factory_hr);
    payload += R"(","guarded_swap_chain_create_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_create_hr);
    payload += R"(","guarded_swap_chain_query_hresult":")";
    payload += hresult_hex(target->guarded_swap_chain_query_hr);
    payload += R"(","guarded_back_buffer_0_hresult":")";
    payload += hresult_hex(target->guarded_back_buffer_0_hr);
    payload += R"(","guarded_back_buffer_1_hresult":")";
    payload += hresult_hex(target->guarded_back_buffer_1_hr);
    payload += R"(","guarded_barrier_clear_allocator_reset_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_allocator_reset_hr);
    payload += R"(","guarded_barrier_clear_command_list_reset_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_command_list_reset_hr);
    payload += R"(","guarded_barrier_clear_command_list_close_hresult":")";
    payload += hresult_hex(target->guarded_barrier_clear_command_list_close_hr);
    payload += R"(","guarded_clear_pass_fence_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_fence_hr);
    payload += R"(","guarded_clear_pass_signal_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_signal_hr);
    payload += R"(","guarded_clear_pass_set_event_hresult":")";
    payload += hresult_hex(target->guarded_clear_pass_set_event_hr);
    payload += R"("})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API void gr_renderer_d3d12_destroy_diagnostic_context(void* context) {
    delete context_from_handle(context);
}

}

