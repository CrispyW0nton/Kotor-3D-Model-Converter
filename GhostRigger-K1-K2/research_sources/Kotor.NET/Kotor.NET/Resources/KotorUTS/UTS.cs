using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTS
{
    public class UTS
    {
        public string Tag { get; set; } = "";
        public LocalizedString LocName { get; set; } = new();
        public ResRef TemplateResRef { get; set; } = "";
        public byte Active { get; set; }
        public byte Continuous { get; set; }
        public byte Looping { get; set; }
        public byte Positional { get; set; }
        public byte RandomPosition { get; set; }
        public byte Random { get; set; }
        public float Elevation { get; set; }
        public float MaxDistance { get; set; }
        public float MinDistance { get; set; }
        public float RandomRangeX { get; set; }
        public float RandomRangeY { get; set; }
        public uint Interval { get; set; }
        public uint IntervalVrtn { get; set; }
        public float PitchVariation { get; set; }
        public byte Priority { get; set; }
        public uint Hours { get; set; }
        public byte Times { get; set; }
        public byte Volume { get; set; }
        public byte VolumeVrtn { get; set; }
        public List<ResRef> Sounds { get; set; } = new();
        public byte PaletteID { get; set; }
        public string Comment { get; set; } = "";
    }

}
