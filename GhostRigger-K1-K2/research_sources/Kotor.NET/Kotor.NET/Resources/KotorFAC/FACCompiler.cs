using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorFAC
{
    public class FACCompiler : IGFFDecompiler<FAC>
    {
        private GFF _gff;

        public FACCompiler(GFF gff)
        {
            _gff = gff;
        }

        public FAC Decompile()
        {
            var fac = new FAC
            {
                FactionList = _gff.Root.GetList("FactionList", new()).Select(gffFaction => new Faction
                {
                    FactionParentID = gffFaction.GetInt32("FactionParentID", 0),
                    FactionName = gffFaction.GetString("FactionName", ""),
                    FactionGlobal = gffFaction.GetUInt8("FactionGlobal", 0) != 0
                }).ToList(),

                RepList = _gff.Root.GetList("RepList", new()).Select(gffRep => new Reputation
                {
                    FactionID1 = gffRep.GetInt32("FactionID1", 0),
                    FactionID2 = gffRep.GetInt32("FactionID2", 0),
                    FactionRep = gffRep.GetInt32("FactionRep", 0),
                }).ToList(),
            };

            return fac;
        }
    }
}
