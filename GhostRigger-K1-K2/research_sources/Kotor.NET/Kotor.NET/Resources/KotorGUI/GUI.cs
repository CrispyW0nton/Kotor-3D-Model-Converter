using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;

namespace Kotor.NET.Resources.KotorGUI
{
    public class GUI
    {
        public List<Control> Controls { get; set; } = new();
        public int ControlType { get; set; }
        public Byte Obj_Locked { get; set; }
        public string Tag { get; set; } = "";
        public int Obj_ParentID { get; set; }
        public Extent EXTENT { get; set; } = new();
        public float ALPHA { get; set; }
        public Border BORDER { get; set; } = new();
        public Vector3 Color { get; set; } = new();
        public int Obj_Layer { get; set; }
    }

    public class Control
    {
        public int ControlType { get; set; }
        public int ID { get; set; }
        public byte Obj_Locked { get; set; }
        public string Obj_Parent { get; set; } = "";
        public string Tag { get; set; } = "";
        public int Obj_ParentID { get; set; }
        public int Obj_Layer { get; set; }
        public Extent EXTENT { get; set; } = new();
        public Border BORDER { get; set; } = new();
        public Text TEXT { get; set; } = new();
        public Hilight HILIGHT { get; set; } = new();
        public MoveTo MOVETO { get; set; } = new();
        public Vector3 COLOR { get; set; } = new();
        public byte LOOPING { get; set; }
        public int PADDING { get; set; }
        public ProtoItem PROTOITEM { get; set; } = new();
        public Scrollbar SCROLLBAR { get; set; } = new();
        public byte LEFTSCROLLBAR { get; set; }
        public int MAXVALUE { get; set; }
        public Thumb THUMB { get; set; } = new();
        public int CURVALUE { get; set; }
        public Progress PROGRESS { get; set; } = new();
        public byte STARTFROMLEFT { get; set; }
        public Selected SELECTED { get; set; } = new();
        public HilightSelected HILIGHTSELECTED { get; set; } = new();
        public byte ISSELECTED { get; set; }
        public int PARENTID { get; set; }
    }

    public class Extent
    {
        public int LEFT { get; set; }
        public int TOP { get; set; }
        public int WIDTH { get; set; }
        public int HEIGHT { get; set; }
    }

    public class Border
    {
        public string CORNER { get; set; } = "";
        public string EDGE { get; set; } = "";
        public string FILL { get; set; } = "";
        public int FILLSTYLE { get; set; }
        public int DIMENSION { get; set; }
        public int INNEROFFSET { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public byte PULSING { get; set; }
        public int INNEROFFSETY { get; set; }
    }

    public class Text
    {
        public int ALIGNMENT { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public string FONT { get; set; } = "";
        public string TEXT { get; set; } = "";
        public uint STRREF { get; set; }
        public byte PULSING { get; set; }
    }

    public class Hilight
    {
        public ResRef CORNER { get; set; } = "";
        public ResRef EDGE { get; set; } = "";
        public ResRef FILL { get; set; } = "";
        public int FILLSTYLE { get; set; }
        public int DIMENSION { get; set; }
        public int INNEROFFSET { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public byte PULSING { get; set; }
        public int INNEROFFSETY { get; set; }
    }

    public class MoveTo
    {
        public int DOWN { get; set; }
        public int LEFT { get; set; }
        public int RIGHT { get; set; }
        public int UP { get; set; }
    }

    public class ProtoItem
    {
        public int CONTROLTYPE { get; set; }
        public string Obj_Parent { get; set; } = "";
        public string Tag { get; set; } = "";
        public int Obj_ParentID { get; set; }
        public Extent EXTENT { get; set; } = new();
        public Border BORDER { get; set; } = new();
        public Text TEXT { get; set; } = new();
        public Hilight HILIGHT { get; set; } = new();
        public Selected SELECTED { get; set; } = new();
        public HilightSelected HILIGHTSELECTED { get; set; }
        public byte ISSELECTED { get; set; }
    }

    public class Scrollbar
    {
        public int CONTROLTYPE { get; set; }
        public string Obj_Parent { get; set; } = "";
        public string Tag { get; set; } = "";
        public int Obj_ParentID { get; set; }
        public Extent EXTENT { get; set; } = new();
        public Border BORDER { get; set; } = new();
        public Dir DIR { get; set; } = new();
        public byte DRAWMODE { get; set; }
        public int MAXVALUE { get; set; }
        public int VISIBLEVALUE { get; set; }
        public Thumb THUMB { get; set; } = new();
        public int CURVALUE { get; set; }
    }

    public class Dir
    {
        public string IMAGE { get; set; } = "";
        public int DRAWSTYLE { get; set; }
        public int FLIPSTYLE { get; set; }
        public float ROTATE { get; set; }
        public int ALIGNMENT { get; set; }
        public int ROTATESTYLE { get; set; }
    }

    public class Thumb
    {
        public ResRef IMAGE { get; set; } = "";
        public int DRAWSTYLE { get; set; }
        public int FLIPSTYLE { get; set; }
        public float ROTATE { get; set; }
        public int ALIGNMENT { get; set; }
        public int ROTATESTYLE { get; set; }
    }

    public class Progress
    {
        public ResRef CORNER { get; set; } = "";
        public ResRef EDGE { get; set; } = "";
        public ResRef FILL { get; set; } = "";
        public int FILLSTYLE { get; set; }
        public int DIMENSION { get; set; }
        public int INNEROFFSET { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public byte PULSING { get; set; }
        public int INNEROFFSETY { get; set; }
    }

    public class Selected
    {
        public ResRef CORNER { get; set; } = "";
        public ResRef EDGE { get; set; } = "";
        public ResRef FILL { get; set; } = "";
        public int FILLSTYLE { get; set; }
        public int DIMENSION { get; set; }
        public int INNEROFFSET { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public byte PULSING { get; set; }
        public int INNEROFFSETY { get; set; }
    }

    public class HilightSelected
    {
        public ResRef CORNER { get; set; } = "";
        public ResRef EDGE { get; set; } = "";
        public ResRef FILL { get; set; } = "";
        public Int32 FILLSTYLE { get; set; }
        public Int32 DIMENSION { get; set; }
        public Int32 INNEROFFSET { get; set; }
        public Vector3 COLOR { get; set; } = new();
        public Byte PULSING { get; set; }
        public Int32 INNEROFFSETY { get; set; }
    }
}
