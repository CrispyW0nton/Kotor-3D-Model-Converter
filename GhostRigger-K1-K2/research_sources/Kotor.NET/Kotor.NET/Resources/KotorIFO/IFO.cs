using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Metadata;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Resources.KotorARE;

namespace Kotor.NET.Resources.KotorIFO
{
    public class IFO
    {
        public byte[] Mod_ID { get; set; }
        public int Mod_Creator_ID { get; set; }
        public uint Mod_Version { get; set; }
        public string Mod_VO_ID { get; set; }
        public ushort Expansion_Pack { get; set; }
        public LocalizedString Mod_Name { get; set; } = new();
        public string Mod_Tag { get; set; } = "";
        public string Mod_Hak { get; set; } = "";
        public LocalizedString Mod_Description { get; set; } = new();
        public byte Mod_IsSaveGame { get; set; }
        public ResRef Mod_Entry_Area { get; set; } = "";
        public float Mod_Entry_X { get; set; }
        public float Mod_Entry_Y { get; set; }
        public float Mod_Entry_Z { get; set; }
        public float Mod_Entry_Dir_X { get; set; }
        public float Mod_Entry_Dir_Y { get; set; }
        public List<string> Mod_Expan_List { get; set; } = new();
        public byte Mod_DawnHour { get; set; }
        public byte Mod_DuskHour { get; set; }
        public byte Mod_MinPerHour { get; set; }
        public byte Mod_StartMonth { get; set; }
        public byte Mod_StartDay { get; set; }
        public byte Mod_StartHour { get; set; }
        public uint Mod_StartYear { get; set; }
        public byte Mod_XPScale { get; set; }
        public ResRef Mod_OnHeartbeat { get; set; } = "";
        public ResRef Mod_OnModLoad { get; set; } = "";
        public ResRef Mod_OnModStart { get; set; } = "";
        public ResRef Mod_OnClientEntr { get; set; } = "";
        public ResRef Mod_OnClientLeav { get; set; } = "";
        public ResRef Mod_OnActvtItem { get; set; } = "";
        public ResRef Mod_OnAcquirItem { get; set; } = "";
        public ResRef Mod_OnUsrDefined { get; set; } = "";
        public ResRef Mod_OnUnAqreItem { get; set; } = "";
        public ResRef Mod_OnPlrDeath { get; set; } = "";
        public ResRef Mod_OnPlrDying { get; set; } = "";
        public ResRef Mod_OnPlrLvlUp { get; set; } = "";
        public ResRef Mod_OnSpawnBtnDn { get; set; } = "";
        public ResRef Mod_OnPlrRest { get; set; } = "";
        public ResRef Mod_StartMovie { get; set; } = "";
        public List<ResRef> Mod_Area_list { get; set; } = new();
    }
}
