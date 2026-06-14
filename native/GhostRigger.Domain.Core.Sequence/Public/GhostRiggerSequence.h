#pragma once

#ifdef GHOSTRIGGER_SEQUENCE_EXPORTS
#define GHOSTRIGGER_SEQUENCE_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SEQUENCE_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_version();
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_capabilities_json();
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_owner_boundary_json();
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_dependency_schema_json();
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_interpolation_mode(const char* mode);
GHOSTRIGGER_SEQUENCE_API double gr_sequence_ease(double t, const char* mode);
GHOSTRIGGER_SEQUENCE_API double gr_sequence_lerp_number(double a, double b, double t);
GHOSTRIGGER_SEQUENCE_API double gr_sequence_interpolate_number(double a, double b, double t, const char* mode);
GHOSTRIGGER_SEQUENCE_API int gr_sequence_interpolate_bool(int a, int b, double t, const char* mode);
GHOSTRIGGER_SEQUENCE_API int gr_sequence_clamp_frame(int frame, int start_frame, int end_frame);
GHOSTRIGGER_SEQUENCE_API double gr_sequence_frame_to_seconds(int frame, int start_frame, double frame_rate);
GHOSTRIGGER_SEQUENCE_API int gr_sequence_seconds_to_frame(double seconds, int start_frame, int end_frame, double frame_rate);
GHOSTRIGGER_SEQUENCE_API int gr_sequence_duration_frames(int start_frame, int end_frame);
GHOSTRIGGER_SEQUENCE_API double gr_sequence_duration_seconds(int start_frame, int end_frame, double frame_rate);
GHOSTRIGGER_SEQUENCE_API const char* gr_sequence_contracts_schema_json();
}
