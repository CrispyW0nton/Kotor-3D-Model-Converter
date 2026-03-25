using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Formats.KotorSSF;

namespace Kotor.NET.Patcher.Modifiers.ForGFF.Values
{
    public class TLKMemoryValue : IValue
    {
        public int TokenID { get; set; }

        public TLKMemoryValue(int tokenID)
        {
            TokenID = tokenID;
        }

        public string Resolve(IMemory memory, GFF gff)
        {
            var value = memory.FromTLKToken(TokenID);

            if (value is not null)
            {
                return value.Value.ToString();
            }
            else
            {
                throw new ApplyModifierException($"TLKMemory token {TokenID} does not exist.");
            }
        }
    }
}
