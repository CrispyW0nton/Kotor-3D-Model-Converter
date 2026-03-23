using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTI
{
    public class UTIDecompiler : IGFFCompiler
    {
        private UTI _uti;

        public UTIDecompiler(UTI uti)
        {
            _uti = uti;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetUInt32("AddCost", _uti.AddCost);
            gff.Root.SetInt32("BaseItem", _uti.BaseItem);
            gff.Root.SetUInt8("BodyVariation", _uti.BodyVariation);
            gff.Root.SetUInt8("Charges", _uti.Charges);
            gff.Root.SetString("Comment", _uti.Comment);
            gff.Root.SetUInt32("Cost", _uti.Cost);
            gff.Root.SetLocalizedString("DescIdentified", _uti.DescIdentified);
            gff.Root.SetLocalizedString("Description", _uti.Description);
            gff.Root.SetLocalizedString("LocalizedName", _uti.LocalizedName);
            gff.Root.SetUInt8("ModelVariation", _uti.ModelVariation);
            gff.Root.SetUInt8("PaletteID", _uti.PaletteID);
            gff.Root.SetUInt8("Plot", _uti.Plot);
            gff.Root.SetUInt16("StackSize", _uti.StackSize);
            gff.Root.SetString("Tag", _uti.Tag);
            gff.Root.SetResRef("TemplateResRef", _uti.TemplateResRef);
            gff.Root.SetUInt8("TextureVar", _uti.TextureVar);
            gff.Root.SetUInt8("UpgradeLevel", _uti.UpgradeLevel);
            gff.Root.SetUInt8("Stolen", _uti.Stolen);
            gff.Root.SetUInt8("Identified", _uti.Identified);

            var propertiesList = gff.Root.SetList("PropertiesList", new());
            foreach (var property in _uti.Properties)
            {
                var propStruct = propertiesList.Add();
                propStruct.SetUInt8("CostTable", property.CostTable);
                propStruct.SetUInt16("CostValue", property.CostValue);
                propStruct.SetUInt8("Param1", property.Param1);
                propStruct.SetUInt8("Param1Value", property.Param1Value);
                propStruct.SetUInt16("PropertyName", property.PropertyName);
                propStruct.SetUInt16("Subtype", property.Subtype);
                propStruct.SetUInt8("UpgradeType", property.UpgradeType);
                propStruct.SetUInt8("ChanceAppear", property.ChanceAppear);
            }

            return gff;
        }
    }

}
