# UE5 IK Retargeter Setup for KOTOR Models

GhostRigger Day 4.5 v6 exports KOTOR characters with their native Aurora bind
pose preserved and a UE5-style naming layer applied. Alignment to Manny or Quinn
is handled in Unreal through the IK Rig and IK Retargeter tools.

## Steps

1. Import the GhostRigger FBX into UE5.
2. Create an IK Rig for the imported KOTOR character.
3. Create or open the IK Rig for Manny/Quinn.
4. Create an IK Retargeter with the KOTOR rig and Manny/Quinn rig.
5. Open Edit Retarget Pose.
6. Adjust the KOTOR source pose to match the target mannequin pose.
7. Save the retarget pose.
8. Retarget or preview animations through the IK Retargeter.

This replaces the failed export-time rest-pose forcing approach. The exporter
preserves source semantics; Unreal handles target semantics.
