import json
import asyncio

import pytest


def _payload(result):
    assert result["type"] == "text"
    return json.loads(result["text"])


def test_retargeting_tools_are_registered():
    from src.kotormcp.tools import get_all_tools

    names = {tool["name"] for tool in get_all_tools()}

    assert "ghostrigger_get_retarget_skeleton_info" in names
    assert "ghostrigger_build_retarget_map" in names
    assert "ghostrigger_list_retarget_animations" in names
    assert "ghostrigger_export_unity_fbx" in names


def test_retargeting_skeleton_info_reports_quinn_asset():
    from src.kotormcp.tools import handle_tool
    from src.unreal.quinn import QUINN_BONE_MAP

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    data = _payload(asyncio.run(handle_tool(
        "ghostrigger_get_retarget_skeleton_info",
        {"target_type": "unreal_quinn", "include_nodes": False},
    )))

    assert data["skeleton_type"] == "unreal_quinn"
    assert data["asset"]["name"] == "SKM_Quinn_Simple"
    assert data["asset"]["bone_count"] >= 70
    assert data["node_count"] >= data["asset"]["bone_count"]
    assert data["nodes"] == []


def test_retargeting_map_reports_quinn_to_quinn_matches():
    from src.kotormcp.tools import handle_tool
    from src.unreal.quinn import QUINN_BONE_MAP

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    data = _payload(asyncio.run(handle_tool(
        "ghostrigger_build_retarget_map",
        {"source_type": "unreal_quinn", "target_type": "unreal_quinn"},
    )))

    assert data["source"]["type"] == "unreal_quinn"
    assert data["target"]["type"] == "unreal_quinn"
    assert data["matched_count"] >= 60
    assert data["coverage"]["source_mapped_ratio"] > 0.8
    assert data["mapping"]["pelvis"] == "pelvis"


def test_export_unity_fbx_rejects_out_of_scope_day4_request():
    from src.kotormcp.tools import handle_tool

    data = _payload(asyncio.run(handle_tool(
        "ghostrigger_export_unity_fbx",
        {
            "source_model_resref": "pfbam",
            "target_skeleton_id": "ue5_quinn",
            "clip_names": ["g1a1"],
        },
    )))

    assert data["ok"] is False
    assert "pmbam" in data["error"]
