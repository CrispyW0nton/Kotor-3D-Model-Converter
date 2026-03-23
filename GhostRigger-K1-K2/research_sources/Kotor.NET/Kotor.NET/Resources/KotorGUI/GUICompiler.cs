using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Xml.Linq;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Formats.KotorMDL;

namespace Kotor.NET.Resources.KotorGUI
{
    public class GUICompiler : IGFFDecompiler<GUI>
    {
        private GFF _gff;

        public GUICompiler(GFF gff)
        {
            _gff = gff;
        }

        public GUI Decompile()
        {
            var gui = new GUI
            {
                ControlType = _gff.Root.GetInt32("ControlType", 0),
                Obj_Locked = _gff.Root.GetUInt8("Obj_Locked", 0),
                Tag = _gff.Root.GetString("Tag", ""),
                Obj_ParentID = _gff.Root.GetInt32("Obj_ParentID", 0),
                ALPHA = _gff.Root.GetSingle("ALPHA", 0),
                Obj_Layer = _gff.Root.GetInt32("Obj_Layer", 0),
                Color = _gff.Root.GetVector3("Color", new()),
                EXTENT = new Extent
                {
                    LEFT = _gff.Root.GetStruct("EXTENT").GetInt32("EXTENT_LEFT", 0),
                    TOP = _gff.Root.GetStruct("EXTENT").GetInt32("EXTENT_TOP", 0),
                    WIDTH = _gff.Root.GetStruct("EXTENT").GetInt32("EXTENT_WIDTH", 0),
                    HEIGHT = _gff.Root.GetStruct("EXTENT").GetInt32("EXTENT_HEIGHT", 0)
                },
                BORDER = new Border
                {
                    CORNER = _gff.Root.GetStruct("BORDER").GetString("BORDER_CORNER", ""),
                    EDGE = _gff.Root.GetStruct("BORDER").GetString("BORDER_EDGE", ""),
                    FILL = _gff.Root.GetStruct("BORDER").GetString("BORDER_FILL", ""),
                    FILLSTYLE = _gff.Root.GetStruct("BORDER").GetInt32("BORDER_FILLSTYLE", 0),
                    DIMENSION = _gff.Root.GetStruct("BORDER").GetInt32("BORDER_DIMENSION", 0),
                    INNEROFFSET = _gff.Root.GetStruct("BORDER").GetInt32("BORDER_INNEROFFSET", 0),
                    COLOR = _gff.Root.GetStruct("BORDER").GetVector3("BORDER_COLOR", new()),
                    PULSING = _gff.Root.GetStruct("BORDER").GetUInt8("BORDER_PULSING", 0),
                    INNEROFFSETY = _gff.Root.GetStruct("BORDER").GetInt32("BORDER_INNEROFFSETY", 0)
                },

                Controls = _gff.Root.GetList("Controls").Select(gffControl => new Control
                {
                    ControlType = gffControl.GetInt32("ControlType", 0),
                    ID = gffControl.GetInt32("ID", 0),
                    Obj_Locked = gffControl.GetUInt8("Obj_Locked", 0),
                    Obj_Parent = gffControl.GetString("Obj_Parent", ""),
                    Tag = gffControl.GetString("Tag", ""),
                    Obj_ParentID = gffControl.GetInt32("Obj_ParentID", 0),
                    EXTENT = new Extent
                    {
                        LEFT = gffControl.GetInt32("EXTENT_LEFT", 0),
                        TOP = gffControl.GetInt32("EXTENT_TOP", 0),
                        WIDTH = gffControl.GetInt32("EXTENT_WIDTH", 0),
                        HEIGHT = gffControl.GetInt32("EXTENT_HEIGHT", 0)
                    },
                    BORDER = new Border
                    {
                        CORNER = gffControl.GetString("BORDER_CORNER", ""),
                        EDGE = gffControl.GetString("BORDER_EDGE", ""),
                        FILL = gffControl.GetString("BORDER_FILL", ""),
                        FILLSTYLE = gffControl.GetInt32("BORDER_FILLSTYLE", 0),
                        DIMENSION = gffControl.GetInt32("BORDER_DIMENSION", 0),
                        INNEROFFSET = gffControl.GetInt32("BORDER_INNEROFFSET", 0),
                        COLOR = gffControl.GetVector3("BORDER_COLOR", new()),
                        PULSING = gffControl.GetUInt8("BORDER_PULSING", 0),
                        INNEROFFSETY = gffControl.GetInt32("BORDER_INNEROFFSETY", 0)
                    },
                    TEXT = new Text
                    {
                        ALIGNMENT = gffControl.GetInt32("TEXT_ALIGNMENT", 0),
                        COLOR = gffControl.GetVector3("TEXT_COLOR", new()),
                        FONT = gffControl.GetString("TEXT_FONT", ""),
                        TEXT = gffControl.GetString("TEXT_TEXT", ""),
                        STRREF = gffControl.GetUInt32("TEXT_STRREF", 0),
                        PULSING = gffControl.GetUInt8("TEXT_PULSING", 0)
                    },
                    HILIGHT = new Hilight
                    {
                        CORNER = gffControl.GetString("HILIGHT_CORNER", ""),
                        EDGE = gffControl.GetString("HILIGHT_EDGE", ""),
                        FILL = gffControl.GetString("HILIGHT_FILL", ""),
                        FILLSTYLE = gffControl.GetInt32("HILIGHT_FILLSTYLE", 0),
                        DIMENSION = gffControl.GetInt32("HILIGHT_DIMENSION", 0),
                        INNEROFFSET = gffControl.GetInt32("HILIGHT_INNEROFFSET", 0),
                        COLOR = gffControl.GetVector3("HILIGHT_COLOR", new()),
                        PULSING = gffControl.GetUInt8("HILIGHT_PULSING", 0),
                        INNEROFFSETY = gffControl.GetInt32("HILIGHT_INNEROFFSETY", 0)
                    },
                    MOVETO = new MoveTo
                    {
                        DOWN = gffControl.GetInt32("MOVETO_DOWN", 0),
                        LEFT = gffControl.GetInt32("MOVETO_LEFT", 0),
                        RIGHT = gffControl.GetInt32("MOVETO_RIGHT", 0),
                        UP = gffControl.GetInt32("MOVETO_UP", 0)
                    },
                    COLOR = gffControl.GetVector3("COLOR", new()),
                    LOOPING = gffControl.GetUInt8("LOOPING", 0),
                    PADDING = gffControl.GetInt32("PADDING", 0),
                    PROTOITEM = new ProtoItem
                    {
                        CONTROLTYPE = gffControl.GetInt32("CONTROLTYPE", 0),
                        Obj_Parent = gffControl.GetString("Obj_Parent", ""),
                        Tag = gffControl.GetString("Tag", ""),
                        Obj_ParentID = gffControl.GetInt32("Obj_ParentID", 0),
                        EXTENT = new Extent
                        {
                            LEFT = gffControl.GetInt32("LEFT", 0),
                            TOP = gffControl.GetInt32("TOP", 0),
                            WIDTH = gffControl.GetInt32("WIDTH", 0),
                            HEIGHT = gffControl.GetInt32("HEIGHT", 0)
                        },
                        BORDER = new Border
                        {
                            CORNER = gffControl.GetString("CORNER", ""),
                            EDGE = gffControl.GetString("EDGE", ""),
                            FILL = gffControl.GetString("FILL", ""),
                            FILLSTYLE = gffControl.GetInt32("FILLSTYLE", 0),
                            DIMENSION = gffControl.GetInt32("DIMENSION", 0),
                            INNEROFFSET = gffControl.GetInt32("INNEROFFSET", 0),
                            COLOR = gffControl.GetVector3("COLOR", new()),
                            PULSING = gffControl.GetUInt8("PULSING", 0),
                            INNEROFFSETY = gffControl.GetInt32("INNEROFFSETY", 0)
                        },
                        TEXT = new Text
                        {
                            ALIGNMENT = gffControl.GetInt32("ALIGNMENT", 0),
                            COLOR = gffControl.GetVector3("COLOR", new()),
                            FONT = gffControl.GetString("FONT", ""),
                            TEXT = gffControl.GetString("TEXT", ""),
                            STRREF = gffControl.GetUInt32("STRREF", 0),
                            PULSING = gffControl.GetUInt8("PULSING", 0)
                        },
                        HILIGHT = new Hilight
                        {
                            CORNER = gffControl.GetResRef("CORNER", ""),
                            EDGE = gffControl.GetResRef("EDGE", ""),
                            FILL = gffControl.GetResRef("FILL", ""),
                            FILLSTYLE = gffControl.GetInt32("FILLSTYLE", 0),
                            DIMENSION = gffControl.GetInt32("DIMENSION", 0),
                            INNEROFFSET = gffControl.GetInt32("INNEROFFSET", 0),
                            COLOR = gffControl.GetVector3("COLOR", new()),
                            PULSING = gffControl.GetUInt8("PULSING", 0),
                            INNEROFFSETY = gffControl.GetInt32("INNEROFFSETY", 0)
                        },
                        SELECTED = new Selected
                        {
                            CORNER = gffControl.GetResRef("CORNER", ""),
                            EDGE = gffControl.GetResRef("EDGE", ""),
                            FILL = gffControl.GetResRef("FILL", ""),
                            FILLSTYLE = gffControl.GetInt32("FILLSTYLE", 0),
                            DIMENSION = gffControl.GetInt32("DIMENSION", 0),
                            INNEROFFSET = gffControl.GetInt32("INNEROFFSET", 0),
                            COLOR = gffControl.GetVector3("COLOR", new()),
                            PULSING = gffControl.GetUInt8("PULSING", 0),
                            INNEROFFSETY = gffControl.GetInt32("INNEROFFSETY", 0)
                        },
                        HILIGHTSELECTED = new HilightSelected
                        {
                            CORNER = gffControl.GetResRef("CORNER", new ResRef()),
                            EDGE = gffControl.GetResRef("EDGE", new ResRef()),
                            FILL = gffControl.GetResRef("FILL", new ResRef()),
                            FILLSTYLE = gffControl.GetInt32("FILLSTYLE", 0),
                            DIMENSION = gffControl.GetInt32("DIMENSION", 0),
                            INNEROFFSET = gffControl.GetInt32("INNEROFFSET", 0),
                            COLOR = gffControl.GetVector3("COLOR", new()),
                            PULSING = gffControl.GetUInt8("PULSING", 0),
                            INNEROFFSETY = gffControl.GetInt32("INNEROFFSETY", 0)
                        },
                        ISSELECTED = gffControl.GetUInt8("PROTOITEM_ISSELECTED", 0)
                    },
                    SCROLLBAR = new Scrollbar
                    {
                        CONTROLTYPE = gffControl.GetInt32("SCROLLBAR_CONTROLTYPE", 0),
                        Obj_Parent = gffControl.GetString("SCROLLBAR_Obj_Parent", ""),
                        Tag = gffControl.GetString("SCROLLBAR_Tag", ""),
                        Obj_ParentID = gffControl.GetInt32("SCROLLBAR_Obj_ParentID", 0),
                        EXTENT = new Extent
                        {
                            LEFT = gffControl.GetInt32("SCROLLBAR_EXTENT_LEFT", 0),
                            TOP = gffControl.GetInt32("SCROLLBAR_EXTENT_TOP", 0),
                            WIDTH = gffControl.GetInt32("SCROLLBAR_EXTENT_WIDTH", 0),
                            HEIGHT = gffControl.GetInt32("SCROLLBAR_EXTENT_HEIGHT", 0)
                        },
                        BORDER = new Border
                        {
                            CORNER = gffControl.GetString("SCROLLBAR_BORDER_CORNER", ""),
                            EDGE = gffControl.GetString("SCROLLBAR_BORDER_EDGE", ""),
                            FILL = gffControl.GetString("SCROLLBAR_BORDER_FILL", ""),
                            FILLSTYLE = gffControl.GetInt32("SCROLLBAR_BORDER_FILLSTYLE", 0),
                            DIMENSION = gffControl.GetInt32("SCROLLBAR_BORDER_DIMENSION", 0),
                            INNEROFFSET = gffControl.GetInt32("SCROLLBAR_BORDER_INNEROFFSET", 0),
                            COLOR = gffControl.GetVector3("SCROLLBAR_BORDER_COLOR", new()),
                            PULSING = gffControl.GetUInt8("SCROLLBAR_BORDER_PULSING", 0),
                            INNEROFFSETY = gffControl.GetInt32("SCROLLBAR_BORDER_INNEROFFSETY", 0)
                        },
                        DIR = new Dir
                        {
                            IMAGE = gffControl.GetString("SCROLLBAR_DIR_IMAGE", ""),
                            DRAWSTYLE = gffControl.GetInt32("SCROLLBAR_DIR_DRAWSTYLE", 0),
                            FLIPSTYLE = gffControl.GetInt32("SCROLLBAR_DIR_FLIPSTYLE", 0),
                            ROTATE = gffControl.GetSingle("SCROLLBAR_DIR_ROTATE", 0),
                            ALIGNMENT = gffControl.GetInt32("SCROLLBAR_DIR_ALIGNMENT", 0),
                            ROTATESTYLE = gffControl.GetInt32("SCROLLBAR_DIR_ROTATESTYLE", 0)
                        },
                        DRAWMODE = gffControl.GetUInt8("SCROLLBAR_DRAWMODE", 0),
                        MAXVALUE = gffControl.GetInt32("SCROLLBAR_MAXVALUE", 0),
                        VISIBLEVALUE = gffControl.GetInt32("SCROLLBAR_VISIBLEVALUE", 0),
                        THUMB = new Thumb
                        {
                            IMAGE = gffControl.GetString("SCROLLBAR_THUMB_IMAGE", ""),
                            DRAWSTYLE = gffControl.GetInt32("SCROLLBAR_THUMB_DRAWSTYLE", 0),
                            FLIPSTYLE = gffControl.GetInt32("SCROLLBAR_THUMB_FLIPSTYLE", 0),
                            ROTATE = gffControl.GetSingle("SCROLLBAR_THUMB_ROTATE", 0),
                            ALIGNMENT = gffControl.GetInt32("SCROLLBAR_THUMB_ALIGNMENT", 0),
                            ROTATESTYLE = gffControl.GetInt32("SCROLLBAR_THUMB_ROTATESTYLE", 0)
                        },
                        CURVALUE = gffControl.GetInt32("SCROLLBAR_CURVALUE", 0)
                    },
                    LEFTSCROLLBAR = gffControl.GetUInt8("LEFTSCROLLBAR", 0),
                    MAXVALUE = gffControl.GetInt32("MAXVALUE", 0),
                    THUMB = new Thumb
                    {
                        IMAGE = gffControl.GetStruct("THUMB").GetResRef("IMAGE"),
                        DRAWSTYLE = gffControl.GetStruct("THUMB").GetInt32("DRAWSTYLE"),
                        FLIPSTYLE = gffControl.GetStruct("THUMB").GetInt32("FLIPSTYLE"),
                        ROTATE = gffControl.GetStruct("THUMB").GetSingle("ROTATE"),
                        ALIGNMENT = gffControl.GetStruct("THUMB").GetInt32("ALIGNMENT"),
                        ROTATESTYLE = gffControl.GetStruct("THUMB").GetInt32("ROTATESTYLE"),
                    },
                    CURVALUE = gffControl.GetInt32("CURVALUE", 0),
                    Obj_Layer = gffControl.GetInt32("Obj_Layer", 0),
                    PROGRESS = new Progress
                    {
                        CORNER = gffControl.GetStruct("PROGRESS").GetResRef("CORNER"),
                        EDGE = gffControl.GetStruct("PROGRESS").GetResRef("EDGE"),
                        FILL = gffControl.GetStruct("PROGRESS").GetResRef("FILL"),
                        FILLSTYLE = gffControl.GetStruct("PROGRESS").GetInt32("FILLSTYLE"),
                        DIMENSION = gffControl.GetStruct("PROGRESS").GetInt32("DIMENSION"),
                        INNEROFFSET = gffControl.GetStruct("PROGRESS").GetInt32("INNEROFFSET"),
                        COLOR = gffControl.GetStruct("PROGRESS").GetVector3("COLOR"),
                        PULSING = gffControl.GetStruct("PROGRESS").GetUInt8("PULSING"),
                        INNEROFFSETY = gffControl.GetStruct("PROGRESS").GetInt32("INNEROFFSETY"),
                    },
                    STARTFROMLEFT = gffControl.GetUInt8("STARTFROMLEFT", 0),
                    SELECTED = new Selected
                    {
                        CORNER = gffControl.GetStruct("SELECTED").GetResRef("CORNER"),
                        EDGE = gffControl.GetStruct("SELECTED").GetResRef("EDGE"),
                        FILL = gffControl.GetStruct("SELECTED").GetResRef("FILL"),
                        FILLSTYLE = gffControl.GetStruct("SELECTED").GetInt32("FILLSTYLE"),
                        DIMENSION = gffControl.GetStruct("SELECTED").GetInt32("DIMENSION"),
                        INNEROFFSET = gffControl.GetStruct("SELECTED").GetInt32("INNEROFFSET"),
                        COLOR = gffControl.GetStruct("SELECTED").GetVector3("COLOR"),
                        PULSING = gffControl.GetStruct("SELECTED").GetUInt8("PULSING"),
                        INNEROFFSETY = gffControl.GetStruct("SELECTED").GetInt32("INNEROFFSETY"),
                    },
                    HILIGHTSELECTED = new HilightSelected
                    {
                        CORNER = gffControl.GetStruct("HILIGHTSELECTED").GetResRef("CORNER"),
                        EDGE = gffControl.GetStruct("HILIGHTSELECTED").GetResRef("EDGE"),
                        FILL = gffControl.GetStruct("HILIGHTSELECTED").GetResRef("FILL"),
                        FILLSTYLE = gffControl.GetStruct("HILIGHTSELECTED").GetInt32("FILLSTYLE"),
                        DIMENSION = gffControl.GetStruct("HILIGHTSELECTED").GetInt32("DIMENSION"),
                        INNEROFFSET = gffControl.GetStruct("HILIGHTSELECTED").GetInt32("INNEROFFSET"),
                        COLOR = gffControl.GetStruct("HILIGHTSELECTED").GetVector3("COLOR"),
                        PULSING = gffControl.GetStruct("HILIGHTSELECTED").GetUInt8("PULSING"),
                        INNEROFFSETY = gffControl.GetStruct("HILIGHTSELECTED").GetInt32("INNEROFFSETY"),
                    },
                    ISSELECTED = gffControl.GetUInt8("ISSELECTED", 0),
                    PARENTID = gffControl.GetInt32("PARENTID", 0),

                }).ToList(),
            };

            return gui;
        }
    }
}
