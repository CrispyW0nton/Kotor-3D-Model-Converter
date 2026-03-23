using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Patcher.Modifiers.ForGFF.Values
{
    public class ConstantValue : IValue
    {
        public int StringRef { get; set; }

        public ConstantValue(int stringRef)
        {
            StringRef = stringRef;
        }

        public string Resolve(IMemory memory, GFF gff)
        {
            return StringRef.ToString();
        }
    }
}
