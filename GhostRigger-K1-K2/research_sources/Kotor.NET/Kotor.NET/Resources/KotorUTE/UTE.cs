using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTE
{
    public class UTE
    {
        public string Tag { get; set; } = "";
        public LocalizedString LocalizedName { get; set; } = new();
        public ResRef TemplateResRef { get; set; } = "";
        public byte Active { get; set; }
        public int Difficulty { get; set; }
        public int DifficultyIndex { get; set; }
        public uint Faction { get; set; }
        public int MaxCreatures { get; set; }
        public byte PlayerOnly { get; set; }
        public int RecCreatures { get; set; }
        public byte Reset { get; set; }
        public int ResetTime { get; set; }
        public int Respawns { get; set; }
        public int SpawnOption { get; set; }
        public ResRef OnEntered { get; set; } = "";
        public ResRef OnExit { get; set; } = "";
        public ResRef OnExhausted { get; set; } = "";
        public ResRef OnHeartbeat { get; set; } = "";
        public ResRef OnUserDefined { get; set; } = "";
        public byte PaletteID { get; set; }
        public string Comment { get; set; } = "";
        public List<UTECreature> Creatures { get; set; } = new();
    }

    public class UTECreature
    {
        public int Appearance { get; set; }
        public float CR { get; set; }
        public ResRef ResRef { get; set; } = "";
        public byte SingleSpawn { get; set; }
        public int GuaranteedCount { get; set; }
    }

}
