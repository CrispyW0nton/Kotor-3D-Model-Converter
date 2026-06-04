#pragma once

#include <cstdint>

namespace ghostrigger::runtime::device_resources {

constexpr std::uint32_t kResourceStateMissing = 0U;
constexpr std::uint32_t kResourceStateUpload = 1U;
constexpr std::uint32_t kResourceStateVertexBuffer = 2U;
constexpr std::uint32_t kResourceStateIndexBuffer = 3U;
constexpr std::uint32_t kResourceStateShaderResource = 4U;

constexpr std::uint32_t kStatusReady = 1U;
constexpr std::uint32_t kStatusMissing = 2U;
constexpr std::uint32_t kStatusReused = 4U;

struct TransitionResult {
    std::uint32_t before_state = kResourceStateMissing;
    std::uint32_t after_state = kResourceStateMissing;
    std::uint32_t status = kStatusMissing;
    bool transitioned = false;
    bool already_ready = false;
    bool missing_upload = true;
};

bool ensure_handle(std::uint64_t& handle, std::uint64_t& next_handle);
bool generation_matches(std::uint64_t stored_generation, std::uint64_t generation);
bool upload_matches(std::uint64_t handle, std::uint64_t uploaded_generation, std::uint64_t generation);
void mark_uploaded(std::uint64_t generation, std::uint64_t& uploaded_generation, std::uint32_t& state);
TransitionResult transition_uploaded_resource(
    std::uint64_t handle,
    std::uint64_t uploaded_generation,
    std::uint64_t generation,
    std::uint32_t desired_state,
    std::uint32_t& current_state
);

} // namespace ghostrigger::runtime::device_resources
