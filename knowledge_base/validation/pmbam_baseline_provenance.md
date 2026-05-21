# PMBAM Viewport Baseline Provenance

Date: 2026-05-21
Sprint: 3 R2.75

## Source

- MDL: `tests/fixtures/kotor_stock/k1/pmbam.mdl`
- MDX sibling: `tests/fixtures/kotor_stock/k1/pmbam.mdx`
- Source corpus: isolated stock KOTOR fixture corpus
- MDL SHA-256: `f439fbdbf9e50ef994d14c333d0829017ad72bcfc1bf6f922420943e37ebf3f1`

## Captures

- Front bind pose: `exports/calibration/baselines/pmbam_frame_0000.png`
- Front bind manifest: `exports/calibration/baselines/pmbam_validation.json`
- Three-quarter bind pose: `exports/calibration/baselines/three_quarter/pmbam_frame_0000.png`
- Side-left bind pose: `exports/calibration/baselines/side_left/pmbam_frame_0000.png`
- `g1a1` animation samples: `exports/calibration/baselines/g1a1/`

## Commands

```powershell
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --frames 0 --output exports\calibration\baselines --camera front_ortho
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --frames 0 --output exports\calibration\baselines\three_quarter --camera three_quarter
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --frames 0 --output exports\calibration\baselines\side_left --camera side_left
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --animation g1a1 --frames 0,30,60,90,120 --output exports\calibration\baselines\g1a1 --camera front_ortho
```

## Result

All capture commands completed successfully. The validator reported 61 nodes, 44 meshes, and 267 inherited animations through the fixture supermodel chain.
