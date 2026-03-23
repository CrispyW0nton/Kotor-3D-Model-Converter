using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTM
{
    public class UTMDecompiler : IGFFCompiler
    {
        private UTM _utm;

        public UTMDecompiler(UTM utm)
        {
            _utm = utm;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetResRef("ResRef", _utm.ResRef);
            gff.Root.SetLocalizedString("LocName", _utm.LocName);
            gff.Root.SetString("Tag", _utm.Tag);
            gff.Root.SetInt32("MarkUp", _utm.MarkUp);
            gff.Root.SetInt32("MarkDown", _utm.MarkDown);
            gff.Root.SetResRef("OnOpenStore", _utm.OnOpenStore);
            gff.Root.SetUInt8("BuySellFlag", _utm.BuySellFlag);
            gff.Root.SetString("Comment", _utm.Comment);
            gff.Root.SetUInt8("ID", _utm.ID);

            var itemList = gff.Root.SetList("ItemList", new());
            foreach (var item in _utm.ItemList)
            {
                var itemNode = itemList.Add();
                itemNode.SetResRef("InventoryRes", item.InventoryRes);
                itemNode.SetUInt8("Infinite", item.Infinite);
            }

            return gff;
        }
    }
}
