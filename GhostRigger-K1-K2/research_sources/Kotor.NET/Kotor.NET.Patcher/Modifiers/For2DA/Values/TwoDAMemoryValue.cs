using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Values
{
    /// <summary>
    /// Gets the value from the 2DA memory using the stored token ID.
    /// </summary>
    public class TwoDAMemoryValue : IValue
    {
        /// <summary>
        /// The token ID to search for in the 2DA memory.
        /// </summary>
        public int TokenID { get; set; }

        public TwoDAMemoryValue(int tokenID)
        {
            TokenID = tokenID;
        }

        public string GetValue(IMemory memory, ILogger logger, TwoDA twoda, TwoDARow? row, string? columnHeader)
        {
            var value = memory.From2DAToken(TokenID);

            if (value is not null)
            {
                return value;
            }
            else
            {
                throw new ApplyModifierException($"2DAMemory token {TokenID} does not exist.");
            }
        }
    }
}
