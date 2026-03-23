using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTI
{
    public class UTICompiler : IGFFDecompiler<UTI>
    {
        private GFF _gff;

        public UTICompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTI Decompile()
        {
            var uti = new UTI
            {
                AddCost = _gff.Root.GetUInt32("AddCost", 0),
                BaseItem = _gff.Root.GetInt32("BaseItem", 0),
                BodyVariation = _gff.Root.GetUInt8("BodyVariation", 0),
                Charges = _gff.Root.GetUInt8("Charges", 0),
                Comment = _gff.Root.GetString("Comment", ""),
                Cost = _gff.Root.GetUInt32("Cost", 0),
                DescIdentified = _gff.Root.GetLocalizedString("DescIdentified", new LocalizedString()),
                Description = _gff.Root.GetLocalizedString("Description", new LocalizedString()),
                LocalizedName = _gff.Root.GetLocalizedString("LocalizedName", new LocalizedString()),
                ModelVariation = _gff.Root.GetUInt8("ModelVariation", 0),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Plot = _gff.Root.GetUInt8("Plot", 0),
                StackSize = _gff.Root.GetUInt16("StackSize", 0),
                Tag = _gff.Root.GetString("Tag", ""),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new ResRef()),
                TextureVar = _gff.Root.GetUInt8("TextureVar", 0),
                UpgradeLevel = _gff.Root.GetUInt8("UpgradeLevel", 0),
                Stolen = _gff.Root.GetUInt8("Stolen", 0),
                Identified = _gff.Root.GetUInt8("Identified", 0),

                Properties = _gff.Root.GetList("PropertiesList").Select(node => new UTIProperty
                {
                    CostTable = node.GetUInt8("CostTable", 0),
                    CostValue = node.GetUInt16("CostValue", 0),
                    Param1 = node.GetUInt8("Param1", 0),
                    Param1Value = node.GetUInt8("Param1Value", 0),
                    PropertyName = node.GetUInt16("PropertyName", 0),
                    Subtype = node.GetUInt16("Subtype", 0),
                    UpgradeType = node.GetUInt8("UpgradeType", 0),
                    ChanceAppear = node.GetUInt8("ChanceAppear", 0)
                }).ToList(),
            };

            return uti;
        }
    }

}
