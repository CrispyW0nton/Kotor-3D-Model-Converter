using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorFAC
{
    public class FACDecompiler : IGFFCompiler
    {
        private FAC _fac;

        public FACDecompiler(FAC fac)
        {
            _fac = fac;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            var factionList = gff.Root.SetList("FactionList", new GFFList());
            foreach (var faction in _fac.FactionList)
            {
                var factionNode = factionList.Add();
                factionNode.SetInt32("FactionParentID", faction.FactionParentID);
                factionNode.SetString("FactionName", faction.FactionName);
                factionNode.SetUInt8("FactionGlobal", faction.FactionGlobal ? (byte)1 : (byte)0);
            }

            var repList = gff.Root.SetList("RepList", new GFFList());
            foreach (var rep in _fac.RepList)
            {
                var repNode = repList.Add();
                repNode.SetInt32("FactionID1", rep.FactionID1);
                repNode.SetInt32("FactionID2", rep.FactionID2);
                repNode.SetInt32("FactionRep", rep.FactionRep);
            }

            return gff;
        }
    }
}
