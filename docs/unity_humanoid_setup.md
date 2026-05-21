# Unity Humanoid Avatar Setup for KOTOR Models

GhostRigger Day 4.5 v6 exports the KOTOR/Aurora native bind pose. The FBX uses
UE5-style humanoid bone names, but it does not force Manny/Quinn rest rotations.
Pose interpretation belongs in Unity's Avatar configuration.

## Steps

1. Import the FBX into Unity.
2. Open the model import settings.
3. On the Rig tab, set Animation Type to Humanoid.
4. Set Avatar Definition to Create From This Model.
5. Click Configure and verify the humanoid bone mapping.
6. Use Unity's pose tools only if your project requires a stricter avatar pose.
7. Apply the import settings.

Mecanim can work with a configured humanoid avatar even when the source asset is
not authored in a perfect T-pose. The exported GhostRigger FBX keeps KOTOR
geometry and bind semantics intact so Unity can own avatar setup.
