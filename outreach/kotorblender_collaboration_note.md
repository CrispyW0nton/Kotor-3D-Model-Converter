# Draft Outreach: UE5-to-KOTOR Retargeting Verification

Hello,

I'm working on GhostRigger, a Python/Qt KOTOR MDL tooling project, and we are
building a UE5/Manny-style animation to KOTOR Aurora character retargeting
pipeline. KotorBlender has been one of the most useful public references for
understanding KOTOR's object-as-bone animation model and MDL animation write
semantics.

The specific thing we are trying to validate is not KOTOR-to-Blender import in
general, but whether an externally authored UE5 animation can be converted into
absolute parent-relative Aurora animation controllers without deformation.

Current verification stack:

- GhostRigger reader/writer round-trip on stock PMBAM and `S_Male02`
- Synthetic one-bone FBX tests for exact transform preservation
- KotorBlender export comparison as an external writer oracle
- Viewport render comparison before any live in-game Patch Manager test

If you have guidance on edge cases around animation controller ordering,
quaternion conventions, or how KotorBlender handles dummy-object rest transforms
for facial/talk animations, I would be grateful. The goal is to keep the
implementation clean-room while using public behavior as a correctness reference.

Thanks for maintaining the tooling that made this line of work possible.
