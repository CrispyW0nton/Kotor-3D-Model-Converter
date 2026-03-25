using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patcher.Modifiers.ForSSF;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Values
{
    /// <summary>
    /// Gets the value from the TLK memory using the stored token ID.
    /// </summary>
    public class TLKMemoryValue : IValue
    {
        /// <summary>
        /// The token ID to search for in the TLK memory.
        /// </summary>
        public int TokenID { get; set; }

        public TLKMemoryValue(int tokenID)
        {
            TokenID = tokenID;
        }

        public string GetValue(IMemory memory, ILogger logger, TwoDA twoda, TwoDARow? row, string? columnHeader)
        {
            var value = memory.FromTLKToken(TokenID);

            if (value is not null)
            {
                return value.ToString()!;
            }
            else
            {
                throw new ApplyModifierException($"TLKMemory token {TokenID} does not exist.");
            }
        }
    }
}
