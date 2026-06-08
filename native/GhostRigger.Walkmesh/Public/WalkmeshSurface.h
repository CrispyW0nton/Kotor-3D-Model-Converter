#pragma once

namespace ghostrigger::walkmesh::core::walkmesh::surface {

struct Rgba {
    double r;
    double g;
    double b;
    double a;
};

struct Rgb {
    double r;
    double g;
    double b;
};

const char* surface_name(int surface_id) noexcept;
Rgba surface_color(int surface_id) noexcept;
bool is_walkable(int surface_id) noexcept;
bool is_non_walkable(int surface_id) noexcept;
const char* fbx_material_name(int surface_id) noexcept;
Rgb fbx_material_diffuse(int surface_id) noexcept;
const char* walkmesh_surface_contracts_schema_json() noexcept;

} // namespace ghostrigger::walkmesh::core::walkmesh::surface
