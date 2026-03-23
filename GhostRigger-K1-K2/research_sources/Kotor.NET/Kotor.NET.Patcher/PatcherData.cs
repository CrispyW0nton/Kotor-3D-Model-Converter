using Kotor.NET.Common.Data;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Formats.KotorSSF;
using Kotor.NET.Formats.KotorTLK;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher
{
    public class PatcherData
    {
        public List<ModifyFile<TwoDA>> TwoDAFiles { get; set; } = new();
        public List<ModifyFile<GFF>> GFFFiles { get; set; } = new();
        public List<ModifyFile<SSF>> SSFFiles { get; set; } = new();
        public ModifyFile<TLK> TLKFiles { get; set; } = new();
    }
}
