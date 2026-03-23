using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorGUI
{
    public class GUIDecompiler : IGFFCompiler
    {
        private GUI _gui;

        public GUIDecompiler(GUI gui)
        {
            _gui = gui;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            var gffRoot = gff.Root;

            gffRoot.SetInt32("ControlType", _gui.ControlType);
            gffRoot.SetUInt8("Obj_Locked", _gui.Obj_Locked);
            gffRoot.SetString("Tag", _gui.Tag);
            gffRoot.SetInt32("Obj_ParentID", _gui.Obj_ParentID);
            gffRoot.SetSingle("ALPHA", _gui.ALPHA);
            gffRoot.SetVector3("Color", _gui.Color);
            gffRoot.SetInt32("Obj_Layer", _gui.Obj_Layer);

            var extentRootNode = gffRoot.SetStruct("EXTENT", new());
            extentRootNode.SetInt32("LEFT", _gui.EXTENT.LEFT);
            extentRootNode.SetInt32("TOP", _gui.EXTENT.TOP);
            extentRootNode.SetInt32("WIDTH", _gui.EXTENT.WIDTH);
            extentRootNode.SetInt32("HEIGHT", _gui.EXTENT.HEIGHT);

            var borderRootNode = gffRoot.SetStruct("BORDER", new());
            borderRootNode.SetString("CORNER", _gui.BORDER.CORNER);
            borderRootNode.SetString("EDGE", _gui.BORDER.EDGE);
            borderRootNode.SetString("FILL", _gui.BORDER.FILL);
            borderRootNode.SetInt32("FILLSTYLE", _gui.BORDER.FILLSTYLE);
            borderRootNode.SetInt32("DIMENSION", _gui.BORDER.DIMENSION);
            borderRootNode.SetInt32("INNEROFFSET", _gui.BORDER.INNEROFFSET);
            borderRootNode.SetVector3("COLOR", _gui.BORDER.COLOR);
            borderRootNode.SetUInt8("PULSING", _gui.BORDER.PULSING);
            borderRootNode.SetInt32("INNEROFFSETY", _gui.BORDER.INNEROFFSETY);

            var gffControls = gffRoot.SetList("Controls", new());
            foreach (var control in _gui.Controls)
            {
                var gffControl = gffControls.Add();
                gffControl.SetInt32("ControlType", control.ControlType);
                gffControl.SetInt32("ID", control.ID);
                gffControl.SetUInt8("Obj_Locked", control.Obj_Locked);
                gffControl.SetString("Obj_Parent", control.Obj_Parent);
                gffControl.SetString("Tag", control.Tag);
                gffControl.SetInt32("Obj_ParentID", control.Obj_ParentID);
                gffControl.SetInt32("Obj_Layer", control.Obj_Layer);

                var extentNode = gffControl.SetStruct("EXTENT", new());
                extentNode.SetInt32("LEFT", control.EXTENT.LEFT);
                extentNode.SetInt32("TOP", control.EXTENT.TOP);
                extentNode.SetInt32("WIDTH", control.EXTENT.WIDTH);
                extentNode.SetInt32("HEIGHT", control.EXTENT.HEIGHT);

                var borderNode = gffControl.SetStruct("BORDER", new());
                borderNode.SetString("CORNER", control.BORDER.CORNER);
                borderNode.SetString("EDGE", control.BORDER.EDGE);
                borderNode.SetString("FILL", control.BORDER.FILL);
                borderNode.SetInt32("FILLSTYLE", control.BORDER.FILLSTYLE);
                borderNode.SetInt32("DIMENSION", control.BORDER.DIMENSION);
                borderNode.SetInt32("INNEROFFSET", control.BORDER.INNEROFFSET);
                borderNode.SetVector3("COLOR", control.BORDER.COLOR);
                borderNode.SetUInt8("PULSING", control.BORDER.PULSING);
                borderNode.SetInt32("INNEROFFSETY", control.BORDER.INNEROFFSETY);

                var textNode = gffControl.SetStruct("TEXT", new());
                textNode.SetInt32("ALIGNMENT", control.TEXT.ALIGNMENT);
                textNode.SetVector3("COLOR", control.TEXT.COLOR);
                textNode.SetString("FONT", control.TEXT.FONT);
                textNode.SetString("TEXT", control.TEXT.TEXT);
                textNode.SetUInt32("STRREF", control.TEXT.STRREF);
                textNode.SetUInt8("PULSING", control.TEXT.PULSING);

                var hilightNode = gffControl.SetStruct("HILIGHT", new());
                //hilightNode.SetString("CORNER", control.HILIGHT.CORNER);
                //hilightNode.SetString("EDGE", control.HILIGHT.EDGE);
                //hilightNode.SetString("FILL", control.HILIGHT.FILL);
                hilightNode.SetInt32("FILLSTYLE", control.HILIGHT.FILLSTYLE);
                hilightNode.SetInt32("DIMENSION", control.HILIGHT.DIMENSION);
                hilightNode.SetInt32("INNEROFFSET", control.HILIGHT.INNEROFFSET);
                hilightNode.SetVector3("COLOR", control.HILIGHT.COLOR);
                hilightNode.SetUInt8("PULSING", control.HILIGHT.PULSING);
                hilightNode.SetInt32("INNEROFFSETY", control.HILIGHT.INNEROFFSETY);

                var moveToNode = gffControl.SetStruct("MOVETO", new());
                moveToNode.SetInt32("DOWN", control.MOVETO.DOWN);
                moveToNode.SetInt32("LEFT", control.MOVETO.LEFT);
                moveToNode.SetInt32("RIGHT", control.MOVETO.RIGHT);
                moveToNode.SetInt32("UP", control.MOVETO.UP);

                gffControl.SetVector3("COLOR", control.COLOR);
                gffControl.SetUInt8("LOOPING", control.LOOPING);
                gffControl.SetInt32("PADDING", control.PADDING);

                var protoItemNode = gffControl.SetStruct("PROTOITEM", new());
                protoItemNode.SetInt32("CONTROLTYPE", control.PROTOITEM.CONTROLTYPE);
                protoItemNode.SetString("Obj_Parent", control.PROTOITEM.Obj_Parent);
                protoItemNode.SetString("Tag", control.PROTOITEM.Tag);
                protoItemNode.SetInt32("Obj_ParentID", control.PROTOITEM.Obj_ParentID);

                var protoItemExtentNode = protoItemNode.SetStruct("EXTENT", new());
                protoItemExtentNode.SetInt32("LEFT", control.PROTOITEM.EXTENT.LEFT);
                protoItemExtentNode.SetInt32("TOP", control.PROTOITEM.EXTENT.TOP);
                protoItemExtentNode.SetInt32("WIDTH", control.PROTOITEM.EXTENT.WIDTH);
                protoItemExtentNode.SetInt32("HEIGHT", control.PROTOITEM.EXTENT.HEIGHT);

                var protoItemBorderNode = protoItemNode.SetStruct("BORDER", new());
                protoItemBorderNode.SetString("CORNER", control.PROTOITEM.BORDER.CORNER);
                protoItemBorderNode.SetString("EDGE", control.PROTOITEM.BORDER.EDGE);
                protoItemBorderNode.SetString("FILL", control.PROTOITEM.BORDER.FILL);
                protoItemBorderNode.SetInt32("FILLSTYLE", control.PROTOITEM.BORDER.FILLSTYLE);
                protoItemBorderNode.SetInt32("DIMENSION", control.PROTOITEM.BORDER.DIMENSION);
                protoItemBorderNode.SetInt32("INNEROFFSET", control.PROTOITEM.BORDER.INNEROFFSET);
                protoItemBorderNode.SetVector3("COLOR", control.PROTOITEM.BORDER.COLOR);
                protoItemBorderNode.SetUInt8("PULSING", control.PROTOITEM.BORDER.PULSING);
                protoItemBorderNode.SetInt32("INNEROFFSETY", control.PROTOITEM.BORDER.INNEROFFSETY);

                var protoItemTextNode = protoItemNode.SetStruct("TEXT", new());
                protoItemTextNode.SetInt32("ALIGNMENT", control.PROTOITEM.TEXT.ALIGNMENT);
                protoItemTextNode.SetVector3("COLOR", control.PROTOITEM.TEXT.COLOR);
                protoItemTextNode.SetString("FONT", control.PROTOITEM.TEXT.FONT);
                protoItemTextNode.SetString("TEXT", control.PROTOITEM.TEXT.TEXT);
                protoItemTextNode.SetUInt32("STRREF", control.PROTOITEM.TEXT.STRREF);
                protoItemTextNode.SetUInt8("PULSING", control.PROTOITEM.TEXT.PULSING);

                var protoItemHilightNode = protoItemNode.SetStruct("HILIGHT", new());
                //protoItemHilightNode.SetString("CORNER", control.PROTOITEM.HILIGHT.CORNER);
                //protoItemHilightNode.SetString("EDGE", control.PROTOITEM.HILIGHT.EDGE);
                //protoItemHilightNode.SetString("FILL", control.PROTOITEM.HILIGHT.FILL);
                protoItemHilightNode.SetInt32("FILLSTYLE", control.PROTOITEM.HILIGHT.FILLSTYLE);
                protoItemHilightNode.SetInt32("DIMENSION", control.PROTOITEM.HILIGHT.DIMENSION);
                protoItemHilightNode.SetInt32("INNEROFFSET", control.PROTOITEM.HILIGHT.INNEROFFSET);
                protoItemHilightNode.SetVector3("COLOR", control.PROTOITEM.HILIGHT.COLOR);
                protoItemHilightNode.SetUInt8("PULSING", control.PROTOITEM.HILIGHT.PULSING);
                protoItemHilightNode.SetInt32("INNEROFFSETY", control.PROTOITEM.HILIGHT.INNEROFFSETY);

                var selectedNode = gffControl.SetStruct("SELECTED", new());
                selectedNode.SetResRef("CORNER", control.SELECTED.CORNER);
                selectedNode.SetResRef("EDGE", control.SELECTED.EDGE);
                selectedNode.SetResRef("FILL", control.SELECTED.FILL);
                selectedNode.SetInt32("FILLSTYLE", control.SELECTED.FILLSTYLE);
                selectedNode.SetInt32("DIMENSION", control.SELECTED.DIMENSION);
                selectedNode.SetInt32("INNEROFFSET", control.SELECTED.INNEROFFSET);
                selectedNode.SetVector3("COLOR", control.SELECTED.COLOR);
                selectedNode.SetUInt8("PULSING", control.SELECTED.PULSING);
                selectedNode.SetInt32("INNEROFFSETY", control.SELECTED.INNEROFFSETY);

                var hilightSelectedNode = gffControl.SetStruct("HILIGHTSELECTED", new());
                hilightSelectedNode.SetResRef("CORNER", control.HILIGHTSELECTED.CORNER);
                hilightSelectedNode.SetResRef("EDGE", control.HILIGHTSELECTED.EDGE);
                hilightSelectedNode.SetResRef("FILL", control.HILIGHTSELECTED.FILL);
                hilightSelectedNode.SetInt32("FILLSTYLE", control.HILIGHTSELECTED.FILLSTYLE);
                hilightSelectedNode.SetInt32("DIMENSION", control.HILIGHTSELECTED.DIMENSION);
                hilightSelectedNode.SetInt32("INNEROFFSET", control.HILIGHTSELECTED.INNEROFFSET);
                hilightSelectedNode.SetVector3("COLOR", control.HILIGHTSELECTED.COLOR);
                hilightSelectedNode.SetUInt8("PULSING", control.HILIGHTSELECTED.PULSING);
                hilightSelectedNode.SetInt32("INNEROFFSETY", control.HILIGHTSELECTED.INNEROFFSETY);

                gffControl.SetUInt8("ISSELECTED", control.ISSELECTED);
                gffControl.SetInt32("PARENTID", control.PARENTID);
            }

            return gff;
        }
    }

}
