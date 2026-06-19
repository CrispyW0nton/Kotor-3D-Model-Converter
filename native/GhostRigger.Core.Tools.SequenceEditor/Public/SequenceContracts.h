#pragma once

namespace ghostrigger::core::tools::sequenceeditor::contracts {

const char* normalize_interpolation_mode(const char* mode) noexcept;
double ease(double t, const char* mode) noexcept;
double lerp_number(double a, double b, double t) noexcept;
double interpolate_number(double a, double b, double t, const char* mode) noexcept;
int interpolate_bool(int a, int b, double t, const char* mode) noexcept;
int clamp_frame(int frame, int start_frame, int end_frame) noexcept;
double frame_to_seconds(int frame, int start_frame, double frame_rate) noexcept;
int seconds_to_frame(double seconds, int start_frame, int end_frame, double frame_rate) noexcept;
int duration_frames(int start_frame, int end_frame) noexcept;
double duration_seconds(int start_frame, int end_frame, double frame_rate) noexcept;
const char* sequence_contracts_schema_json() noexcept;

} // namespace ghostrigger::core::tools::sequenceeditor::contracts
