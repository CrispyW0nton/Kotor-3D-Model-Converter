using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTT
{
    public class UTT
    {
        public string Tag { get; set; }
        public ResRef TemplateResRef { get; set; } = "";
        public LocalizedString LocalizedName { get; set; } = new();
        public byte AutoRemoveKey { get; set; }
        public uint Faction { get; set; }
        public byte Cursor { get; set; }
        public float HighlightHeight { get; set; }
        public string KeyName { get; set; } = "";
        public ushort LoadScreenID { get; set; }
        public ushort PortraitId { get; set; }
        public int Type { get; set; }
        public byte TrapDetectable { get; set; }
        public byte TrapDetectDC { get; set; }
        public byte TrapDisarmable { get; set; }
        public byte DisarmDC { get; set; }
        public byte TrapFlag { get; set; }
        public byte TrapOneShot { get; set; }
        public byte TrapType { get; set; }
        public ResRef OnDisarm { get; set; } = "";
        public ResRef OnTrapTriggered { get; set; } = "";
        public ResRef OnClick { get; set; } = "";
        public ResRef ScriptHeartbeat { get; set; } = "";
        public ResRef ScriptOnEnter { get; set; } = "";
        public ResRef ScriptOnExit { get; set; } = "";
        public ResRef ScriptUserDefine { get; set; } = "";
        public byte PaletteID { get; set; }
        public string Comment { get; set; } = "";
        public ResRef Portrait { get; set; } = "";
        public string LinkedTo { get; set; } = "";
        public byte PartyRequired { get; set; }
        public byte LinkedToFlags { get; set; }
        public ResRef LinkedToModule { get; set; } = "";
    }

}
