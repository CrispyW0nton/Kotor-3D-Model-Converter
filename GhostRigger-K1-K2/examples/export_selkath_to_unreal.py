#!/usr/bin/env python3
"""
Export Selkath (c_selkath) model to FBX for Unreal Engine

This script demonstrates how to export a KotOR character model with:
- Full skeletal hierarchy
- Skin meshes with vertex weights
- All animations
- Proper bind pose matrices

Usage:
    python examples/export_selkath_to_unreal.py
    
Output:
    c_selkath.fbx - FBX file with skeleton + animations
    rigging/c_selkath.skeleton.json - Bone hierarchy JSON
    rigging/c_selkath.animations.json - Animation list JSON
    rigging/c_selkath.weights.json - Vertex weights JSON
"""

import sys
import os
from pathlib import Path

# Add src to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.resource_manager import ResourceManager
from core.model_data import GameVersion
from converters.mesh_converter import FBXExporter

def export_selkath(kotor_path: str, output_dir: Path):
    """
    Export Selkath model to FBX format for Unreal Engine.
    
    Args:
        kotor_path: Path to KotOR game installation or extracted data
        output_dir: Directory to save FBX and rigging JSON files
    """
    print("=" * 70)
    print("Selkath → Unreal Engine FBX Export")
    print("=" * 70)
    
    # Initialize resource manager
    print(f"\n[1/5] Loading KotOR resources from: {kotor_path}")
    rm = ResourceManager(kotor_path=kotor_path, game_version=GameVersion.K1)
    
    # Load Selkath model (automatically merges supermodel skeleton)
    print("\n[2/5] Loading c_selkath model...")
    model = rm.load_model("c_selkath")
    
    # Display model info
    print(f"      Model name: {model.name}")
    print(f"      Supermodel: {model.supermodel}")
    print(f"      Classification: {model.classification}")
    
    # Count nodes and meshes
    all_nodes = list(model.all_nodes())
    mesh_nodes = [n for n in all_nodes if n.is_mesh or n.is_skin]
    skin_nodes = [n for n in all_nodes if n.is_skin]
    
    print(f"      Total nodes: {len(all_nodes)}")
    print(f"      Mesh nodes: {len(mesh_nodes)}")
    print(f"      Skin nodes (skeleton-bound): {len(skin_nodes)}")
    print(f"      Animations: {len(model.animations)}")
    
    if model.animations:
        print("\n      Animation list:")
        for anim in model.animations[:10]:  # Show first 10
            node_count = len(anim.nodes) if anim.nodes else 0
            print(f"        - {anim.name:20s} {anim.length:6.2f}s  ({node_count:3d} bones)")
        if len(model.animations) > 10:
            print(f"        ... and {len(model.animations) - 10} more animations")
    
    # Check for bone weights
    print("\n[3/5] Analyzing skin weights...")
    total_verts = 0
    weighted_verts = 0
    for node in skin_nodes:
        if node.vertices and node.skin_data:
            total_verts += len(node.vertices)
            weighted_verts += sum(1 for sd in node.skin_data if sd.influences)
    
    if total_verts > 0:
        print(f"      Total vertices: {total_verts}")
        print(f"      Weighted vertices: {weighted_verts} ({weighted_verts/total_verts*100:.1f}%)")
        print(f"      Bone map entries: {len(skin_nodes[0].bone_map) if skin_nodes and skin_nodes[0].bone_map else 0}")
    else:
        print("      ⚠️  WARNING: No skin weights found!")
        print("      This model may not have proper skeleton binding.")
    
    # Export to FBX
    output_dir.mkdir(parents=True, exist_ok=True)
    fbx_path = output_dir / "c_selkath.fbx"
    
    print(f"\n[4/5] Exporting to FBX: {fbx_path}")
    exporter = FBXExporter()
    success = exporter.export(
        model=model,
        fbx_path=str(fbx_path),
        tex_cache=None,
        export_rigging=True  # Also creates rigging/*.json files
    )
    
    if success:
        fbx_size = fbx_path.stat().st_size
        print(f"      ✅ FBX export successful!")
        print(f"      File size: {fbx_size / 1024:.1f} KB")
        
        # Check for AnimationStack entries
        with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            anim_count = content.count('AnimationStack:')
            skin_count = content.count('SubDeformer: "Cluster"')
        print(f"      Animation stacks: {anim_count}")
        print(f"      Skin clusters (bone deformers): {skin_count}")
    else:
        print(f"      ❌ FBX export failed!")
        return False
    
    # Check for rigging JSON files
    print("\n[5/5] Verifying rigging JSON files...")
    rigging_dir = output_dir / "rigging"
    
    expected_files = [
        rigging_dir / "c_selkath.skeleton.json",
        rigging_dir / "c_selkath.animations.json",
        rigging_dir / "c_selkath.weights.json"
    ]
    
    for json_file in expected_files:
        if json_file.exists():
            size = json_file.stat().st_size
            print(f"      ✅ {json_file.name:30s} {size:8,} bytes")
        else:
            print(f"      ❌ {json_file.name:30s} NOT FOUND")
    
    # Final instructions
    print("\n" + "=" * 70)
    print("Export complete! Next steps:")
    print("=" * 70)
    print(f"\n1. Open Unreal Engine project")
    print(f"2. Import: {fbx_path}")
    print(f"3. Import options:")
    print(f"   ✅ Import as Skeletal Mesh")
    print(f"   ✅ Import Animations")
    print(f"   ✅ Import Materials")
    print(f"   ✅ Use T0 as Reference Pose")
    print(f"\n4. Unreal will create:")
    print(f"   - Skeletal Mesh asset (c_selkath)")
    print(f"   - Skeleton asset")
    print(f"   - Animation assets (one per animation)")
    print(f"\n5. Open Animation editor to preview animations")
    print()
    
    return True


def main():
    """Main entry point."""
    # Detect KotOR installation path
    kotor_paths = [
        # Windows Steam
        Path("C:/Program Files (x86)/Steam/steamapps/common/swkotor"),
        Path("C:/Program Files/Steam/steamapps/common/swkotor"),
        # Windows GOG
        Path("C:/GOG Games/Star Wars - KotOR"),
        # Linux Steam
        Path.home() / ".steam/steam/steamapps/common/Knights of the Old Republic",
        # macOS Steam
        Path.home() / "Library/Application Support/Steam/steamapps/common/swkotor",
        # Extracted data directory
        Path("./kotor_data"),
        Path("../kotor_data"),
    ]
    
    # Find first existing path
    kotor_path = None
    for path in kotor_paths:
        if path.exists():
            kotor_path = path
            break
    
    # Or use custom path
    if len(sys.argv) > 1:
        kotor_path = Path(sys.argv[1])
    
    if not kotor_path or not kotor_path.exists():
        print("ERROR: KotOR installation not found!")
        print("\nUsage:")
        print(f"  python {Path(__file__).name} [kotor_path]")
        print("\nExample:")
        print(f"  python {Path(__file__).name} /path/to/kotor")
        print(f"\nSearched paths:")
        for path in kotor_paths:
            print(f"  - {path}")
        sys.exit(1)
    
    # Output directory
    output_dir = PROJECT_ROOT / "output" / "exports"
    
    # Run export
    try:
        success = export_selkath(str(kotor_path), output_dir)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Export failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
