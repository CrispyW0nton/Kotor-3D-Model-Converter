using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorJRL
{
    public class JRLDecompiler : IGFFCompiler
    {
        private JRL _jrl;

        public JRLDecompiler(JRL jrl)
        {
            _jrl = jrl;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            var categoriesList = gff.Root.SetList("Categories", new());
            foreach (var category in _jrl.Categories)
            {
                var categoryNode = categoriesList.Add();
                categoryNode.SetLocalizedString("Name", category.Name);
                categoryNode.SetUInt32("Priority", category.Priority);
                categoryNode.SetString("Comment", category.Comment);
                categoryNode.SetString("Tag", category.Tag);
                categoryNode.SetInt32("PlotIndex", category.PlotIndex);
                categoryNode.SetInt32("PlanetID", category.PlanetID);

                var entryList = categoryNode.SetList("EntryList", new());
                foreach (var entry in category.EntryList)
                {
                    var entryNode = entryList.Add();
                    entryNode.SetUInt32("ID", entry.ID);
                    entryNode.SetUInt16("End", entry.End);
                    entryNode.SetLocalizedString("Text", entry.Text);
                    entryNode.SetSingle("XP_Percentage", entry.XP_Percentage);
                }
            }

            return gff;
        }
    }
}
