using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorSSF;
using Kotor.NET.Patcher.Modifiers.For2DA.Values;

namespace Kotor.NET.Patcher.Modifiers.ForSSF.Values
{
    public class TwoDAMemoryValue : IValue
    {
        public int TokenID { get; set; }

        public TwoDAMemoryValue(int tokenID)
        {
            TokenID = tokenID;
        }

        public int GetValue(IMemory memory, SSF ssf, CreatureSound sound)
        {
            var value = memory.From2DAToken(TokenID);

            if (value is not null)
            {
                int integer;
                var isNumber = int.TryParse(value, out integer);

                if (isNumber)
                {
                    return integer;
                }
                else
                {
                    throw new ApplyModifierException($"2DAMemory token {TokenID} does not contain a valid integer.");
                }
            }
            else
            {
                throw new ApplyModifierException($"2DAMemory token {TokenID} does not exist.");
            }
        }
    }
}
