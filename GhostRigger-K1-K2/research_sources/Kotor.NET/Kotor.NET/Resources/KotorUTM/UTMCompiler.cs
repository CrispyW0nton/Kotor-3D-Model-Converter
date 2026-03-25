using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Formats.KotorMDL;

namespace Kotor.NET.Resources.KotorUTM
{
    public class UTMCompiler : IGFFDecompiler<UTM>
    {
        private GFF _gff;

        public UTMCompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTM Decompile()
        {
            var utm = new UTM
            {
                ResRef = _gff.Root.GetResRef("ResRef"),
                LocName = _gff.Root.GetLocalizedString("LocName"),
                Tag = _gff.Root.GetString("Tag"),
                MarkUp = _gff.Root.GetInt32("MarkUp"),
                MarkDown = _gff.Root.GetInt32("MarkDown"),
                OnOpenStore = _gff.Root.GetResRef("OnOpenStore"),
                BuySellFlag = _gff.Root.GetUInt8("BuySellFlag"),
                Comment = _gff.Root.GetString("Comment"),
                ID = _gff.Root.GetUInt8("ID"),

                ItemList = _gff.Root.GetList("ItemList", new()).Select(gffItem => new UTMItem
                {
                    InventoryRes = gffItem.GetResRef("InventoryRes"),
                    Infinite = gffItem.GetUInt8("Infinite"),
                }).ToList(),
            };

            return utm;
        }
    }
}
