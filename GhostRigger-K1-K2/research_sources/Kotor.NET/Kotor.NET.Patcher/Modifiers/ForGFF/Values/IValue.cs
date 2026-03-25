using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Patcher.Modifiers.ForGFF.Values
{
    public interface IValue
    {
        public string Resolve(IMemory memory, GFF gff);
    }
}
