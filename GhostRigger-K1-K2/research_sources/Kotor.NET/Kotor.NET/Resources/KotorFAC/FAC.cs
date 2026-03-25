using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Resources.KotorFAC
{
    public class Faction
    {
        public int FactionParentID { get; set; }
        public string FactionName { get; set; } = "";
        public bool FactionGlobal { get; set; }
    }

    public class Reputation
    {
        public int FactionID1 { get; set; }
        public int FactionID2 { get; set; }
        public int FactionRep { get; set; }
    }

    public class FAC
    {
        public List<Faction> FactionList { get; set; } = new();
        public List<Reputation> RepList { get; set; } = new();
    }
}
