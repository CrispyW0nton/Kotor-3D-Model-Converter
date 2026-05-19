"""src.autorig – Auto-rigging, AcuRig-style semi-auto, and GRig manual rigging."""

try:
    from .auto_rigger import (
        AutoRigger,
        RigExtractor,
        RigTemplate,
        BoneInfo,
        SkinMeshInfo,
        build_skeleton,
        normalize_skeleton_to_kotor,
        get_bone_colour_map,
    )
except (ImportError, Exception):
    # Graceful fallback when relative imports unavailable (e.g. direct sys.path usage)
    AutoRigger = RigExtractor = RigTemplate = BoneInfo = SkinMeshInfo = None
    build_skeleton = normalize_skeleton_to_kotor = get_bone_colour_map = None

try:
    from .accurig import (
        AcuRig,
        RigGuide,
        BoneMask,
        SymmetryEnforcer,
        WeightPainter,
        ProfileDetector,
        GuidePlacer,
        PoseCorrector,
        PROFILE_HUMANOID,
        PROFILE_QUADRUPED,
        PROFILE_DROID,
        PROFILE_PROP,
        PROFILE_CREATURE,
        HUMANOID_GUIDES,
        QUADRUPED_GUIDES,
        DROID_GUIDES,
        MIRROR_PAIRS,
        BONE_COLOURS,
    )
except (ImportError, Exception):
    AcuRig = RigGuide = BoneMask = SymmetryEnforcer = None
    WeightPainter = ProfileDetector = GuidePlacer = PoseCorrector = None
    PROFILE_HUMANOID = PROFILE_QUADRUPED = PROFILE_DROID = None
    PROFILE_PROP = PROFILE_CREATURE = None
    HUMANOID_GUIDES = QUADRUPED_GUIDES = DROID_GUIDES = None
    MIRROR_PAIRS = BONE_COLOURS = None

try:
    from .grig import (
        GRig,
        BonePin,
        BoneChain,
        BrushMode,
        GRigBrush,
        GRigSymmetry,
        GRigPanelState,
        VertexInfluence,
    )
except (ImportError, Exception):
    GRig = BonePin = BoneChain = BrushMode = None
    GRigBrush = GRigSymmetry = GRigPanelState = VertexInfluence = None

from .cloth_rig import (
    ClothRigConfig,
    ClothRigPreset,
    ClothConstraintPainter,
    ClothRigger,
    ClothRigExporter,
    ClothRigSimulator,
    # M3/T301 — Qt-or-headless cloth preset chooser (replaces the deleted
    # Tk ``ClothRigPanel`` class).
    ClothPresetChoice,
    run_cloth_preset_dialog,
    confirm_cloth_action,
)

__all__ = [
    # Legacy auto-rigger
    "AutoRigger", "RigExtractor", "RigTemplate",
    "BoneInfo", "SkinMeshInfo",
    "build_skeleton", "normalize_skeleton_to_kotor", "get_bone_colour_map",
    # AcuRig system
    "AcuRig", "RigGuide", "BoneMask", "SymmetryEnforcer",
    "WeightPainter", "ProfileDetector", "GuidePlacer", "PoseCorrector",
    "PROFILE_HUMANOID", "PROFILE_QUADRUPED", "PROFILE_DROID",
    "PROFILE_PROP", "PROFILE_CREATURE",
    "HUMANOID_GUIDES", "QUADRUPED_GUIDES", "DROID_GUIDES",
    "MIRROR_PAIRS", "BONE_COLOURS",
    # GRig – Interactive manual rigging system
    "GRig", "BonePin", "BoneChain", "BrushMode",
    "GRigBrush", "GRigSymmetry", "GRigPanelState", "VertexInfluence",
    # Cloth rigging system (K1/K2)
    "ClothRigConfig", "ClothRigPreset", "ClothConstraintPainter",
    "ClothRigger", "ClothRigExporter", "ClothRigSimulator",
    # M3/T301 — Qt-or-headless dialog helpers (replaces ClothRigPanel)
    "ClothPresetChoice", "run_cloth_preset_dialog", "confirm_cloth_action",
]
