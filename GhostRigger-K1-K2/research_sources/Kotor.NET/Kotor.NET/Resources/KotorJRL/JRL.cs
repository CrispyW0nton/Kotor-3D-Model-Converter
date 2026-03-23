using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;

namespace Kotor.NET.Resources.KotorJRL
{
    public class JRL
    {
        public List<JRLCategory> Categories { get; set; } = new List<JRLCategory>();
    }

    public class JRLCategory
    {
        public LocalizedString Name { get; set; }
        public uint Priority { get; set; }
        public string Comment { get; set; }
        public string Tag { get; set; }
        public int PlotIndex { get; set; }
        public int PlanetID { get; set; }
        public List<JRLCategoryEntry> EntryList { get; set; } = new List<JRLCategoryEntry>();
    }

    public class JRLCategoryEntry
    {
        public uint ID { get; set; }
        public ushort End { get; set; }
        public LocalizedString Text { get; set; }
        public float XP_Percentage { get; set; }
    }
}
