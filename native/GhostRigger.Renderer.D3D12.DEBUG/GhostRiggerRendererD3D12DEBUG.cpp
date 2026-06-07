#include "GhostRiggerRendererD3D12.h"

#include <cstring>
#include <iostream>

int main()
{
    const char* version = gr_renderer_d3d12_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Renderer.D3D12 version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_renderer_d3d12_capabilities_json();
    if (std::strstr(capabilities, R"("renderer_backend":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 capabilities missing renderer backend flag" << std::endl;
        return 2;
    }
    if (std::strstr(capabilities, R"("contract_version":"0.1.0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 capabilities missing renderer contract version" << std::endl;
        return 3;
    }
    if (std::strstr(gr_renderer_d3d12_backend_info_json(), R"("api":"d3d12")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 backend info mismatch" << std::endl;
        return 4;
    }
    if (std::strstr(gr_renderer_d3d12_device_requirements_json(), R"("minimum_feature_level":"12_0")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 device requirements mismatch" << std::endl;
        return 5;
    }
    if (std::strstr(gr_renderer_d3d12_adapter_probe_json(), R"("schema":"renderer_d3d12_adapter_probe.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 adapter probe mismatch" << std::endl;
        return 6;
    }
    if (std::strstr(gr_renderer_d3d12_device_readiness_json(), R"("schema":"renderer_d3d12_device_readiness.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 device readiness mismatch" << std::endl;
        return 7;
    }
    if (std::strstr(gr_renderer_d3d12_queue_swap_chain_readiness_json(), R"("schema":"renderer_d3d12_queue_swap_chain_readiness.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 queue/swap-chain readiness mismatch" << std::endl;
        return 8;
    }
    if (std::strstr(gr_renderer_d3d12_failure_diagnostics_json(), R"("schema":"renderer_d3d12_failure_diagnostics.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 failure diagnostics mismatch" << std::endl;
        return 9;
    }
    if (std::strstr(gr_renderer_d3d12_dry_run_frame_stats_json(), R"("backend_id":"renderer_d3d12")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 dry-run frame stats mismatch" << std::endl;
        return 10;
    }
    void* context = gr_renderer_d3d12_create_diagnostic_context();
    const char* context_json = gr_renderer_d3d12_diagnostic_context_json(context);
    if (std::strstr(context_json, R"("schema":"renderer_d3d12_diagnostic_context.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 diagnostic context mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 11;
    }
    if (std::strstr(context_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 diagnostic context enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 12;
    }
    const char* descriptor_allocator_json = gr_renderer_d3d12_descriptor_allocator_readiness_json(context);
    if (std::strstr(
            descriptor_allocator_json,
            R"("schema":"renderer_d3d12_descriptor_allocator_readiness.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 descriptor/allocator readiness mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 13;
    }
    if (std::strstr(descriptor_allocator_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 descriptor/allocator readiness enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 14;
    }
    const char* command_list_json = gr_renderer_d3d12_command_list_readiness_json(context);
    if (std::strstr(command_list_json, R"("schema":"renderer_d3d12_command_list_readiness.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-list readiness mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 15;
    }
    if (std::strstr(command_list_json, R"("command_list_executed":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-list readiness executed a command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 16;
    }
    if (std::strstr(command_list_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-list readiness enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 17;
    }
    const char* surface_swap_chain_json = gr_renderer_d3d12_surface_swap_chain_readiness_json(context, nullptr);
    if (std::strstr(
            surface_swap_chain_json,
            R"("schema":"renderer_d3d12_surface_swap_chain_readiness.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 surface/swap-chain readiness mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 18;
    }
    if (std::strstr(surface_swap_chain_json, R"("native_window_handle_ready":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 surface/swap-chain readiness accepted a null window handle" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 19;
    }
    if (std::strstr(surface_swap_chain_json, R"("present_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 surface/swap-chain readiness enabled present" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 20;
    }
    if (std::strstr(surface_swap_chain_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 surface/swap-chain readiness enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 21;
    }
    const char* render_target_json = gr_renderer_d3d12_render_target_metadata_json(context);
    if (std::strstr(render_target_json, R"("schema":"renderer_d3d12_render_target_metadata.v1")") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 render-target metadata mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 22;
    }
    if (std::strstr(render_target_json, R"("back_buffers_acquired":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 render-target metadata acquired back buffers" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 23;
    }
    if (std::strstr(render_target_json, R"("render_target_views_created":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 render-target metadata created RTVs" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 24;
    }
    if (std::strstr(render_target_json, R"("present_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 render-target metadata enabled present" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 25;
    }
    if (std::strstr(render_target_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 render-target metadata enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 26;
    }
    const char* barrier_clear_pass_json = gr_renderer_d3d12_barrier_clear_pass_metadata_json(context);
    if (std::strstr(
            barrier_clear_pass_json,
            R"("schema":"renderer_d3d12_barrier_clear_pass_metadata.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 barrier/clear-pass metadata mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 27;
    }
    if (std::strstr(barrier_clear_pass_json, R"("resource_barriers_recorded":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 barrier/clear-pass metadata recorded barriers" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 28;
    }
    if (std::strstr(barrier_clear_pass_json, R"("clear_recorded":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 barrier/clear-pass metadata recorded a clear" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 29;
    }
    if (std::strstr(barrier_clear_pass_json, R"("command_list_executed":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 barrier/clear-pass metadata executed a command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 30;
    }
    if (std::strstr(barrier_clear_pass_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 barrier/clear-pass metadata enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 31;
    }
    const char* command_recording_json = gr_renderer_d3d12_command_recording_dry_run_frame_json(context);
    if (std::strstr(
            command_recording_json,
            R"("schema":"renderer_d3d12_command_recording_dry_run_frame.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-recording dry-run metadata mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 32;
    }
    if (std::strstr(command_recording_json, R"("command_list_reset":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-recording dry-run reset a command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 33;
    }
    if (std::strstr(command_recording_json, R"("draw_calls_recorded":0)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-recording dry-run recorded draws" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 34;
    }
    if (std::strstr(command_recording_json, R"("command_list_executed":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-recording dry-run executed a command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 35;
    }
    if (std::strstr(command_recording_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 command-recording dry-run enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 36;
    }
    const char* guarded_recording_json = gr_renderer_d3d12_guarded_command_recording_diagnostics_json(context);
    if (std::strstr(
            guarded_recording_json,
            R"("schema":"renderer_d3d12_guarded_command_recording_diagnostics.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording diagnostics mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 37;
    }
    if (std::strstr(guarded_recording_json, R"("allocator_reset":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording did not reset allocator" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 38;
    }
    if (std::strstr(guarded_recording_json, R"("command_list_reset":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording did not reset command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 39;
    }
    if (std::strstr(guarded_recording_json, R"("command_list_closed":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording did not close command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 40;
    }
    if (std::strstr(guarded_recording_json, R"("draw_calls_recorded":0)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording recorded draws" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 41;
    }
    if (std::strstr(guarded_recording_json, R"("command_list_executed":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording executed a command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 42;
    }
    if (std::strstr(guarded_recording_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 guarded command-recording enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 43;
    }
    const char* no_draw_execution_json = gr_renderer_d3d12_no_draw_execution_fence_diagnostics_json(context);
    if (std::strstr(
            no_draw_execution_json,
            R"("schema":"renderer_d3d12_no_draw_execution_fence_diagnostics.v1")"
        ) == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution/fence diagnostics mismatch" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 44;
    }
    if (std::strstr(no_draw_execution_json, R"("no_draw_command_list_executed":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution did not submit the closed command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 45;
    }
    if (std::strstr(no_draw_execution_json, R"("draw_calls_recorded":0)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution recorded draws" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 46;
    }
    if (std::strstr(no_draw_execution_json, R"("command_lists_submitted":1)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution did not report one submitted command list" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 47;
    }
    if (std::strstr(no_draw_execution_json, R"("fence_signaled":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution did not signal the fence" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 48;
    }
    if (std::strstr(no_draw_execution_json, R"("fence_completed":true)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution did not complete the fence" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 49;
    }
    if (std::strstr(no_draw_execution_json, R"("present_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution enabled present" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 50;
    }
    if (std::strstr(no_draw_execution_json, R"("draw_submission_enabled":false)") == nullptr) {
        std::cerr << "GhostRigger.Renderer.D3D12 no-draw execution enabled draw submission" << std::endl;
        gr_renderer_d3d12_destroy_diagnostic_context(context);
        return 51;
    }
    gr_renderer_d3d12_destroy_diagnostic_context(context);

    std::cout << "GhostRigger.Renderer.D3D12.DEBUG OK: " << version << std::endl;
    return 0;
}
