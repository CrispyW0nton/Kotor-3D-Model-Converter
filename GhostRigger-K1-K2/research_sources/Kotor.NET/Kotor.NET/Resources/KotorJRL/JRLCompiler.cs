using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorJRL
{
    public class JRLCompiler : IGFFDecompiler<JRL>
    {
        private GFF _gff;

        public JRLCompiler(GFF gff)
        {
            _gff = gff;
        }

        public JRL Decompile()
        {
            var jrl = new JRL
            {
                Categories = _gff.Root.GetList("Categories", new()).Select(categoryNode => new JRLCategory
                {
                    Name = categoryNode.GetLocalizedString("Name", new LocalizedString()),
                    Priority = categoryNode.GetUInt32("Priority", 0),
                    Comment = categoryNode.GetString("Comment", ""),
                    Tag = categoryNode.GetString("Tag", ""),
                    PlotIndex = categoryNode.GetInt32("PlotIndex", 0),
                    PlanetID = categoryNode.GetInt32("PlanetID", 0),

                    EntryList = categoryNode.GetList("EntryList", new()).Select(entryNode => new JRLCategoryEntry
                    {
                        ID = entryNode.GetUInt32("ID", 0),
                        End = entryNode.GetUInt16("End", 0),
                        Text = entryNode.GetLocalizedString("Text", new LocalizedString()),
                        XP_Percentage = entryNode.GetSingle("XP_Percentage", 0),
                    }).ToList(),
                }).ToList(),
            };

            return jrl;
        }
    }
}
