using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Values
{
    /// <summary>
    /// Gets a fixed value that is stored on the instance.
    /// </summary>
    public class ConstantValue : IValue
    {
        /// <summary>
        /// The value that will always be returned.
        /// </summary>
        public string Value { get; set; }

        public ConstantValue(string value)
        {
            Value = value;
        }

        public string GetValue(IMemory memory, ILogger logger, TwoDA twoda, TwoDARow? row, string? columnHeader)
        {
            return Value;
        }
    }
}
