using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Values
{
    /// <summary>
    /// Gets the highest integer value plus one under the given column.
    /// </summary>
    public class HighestValue : IValue
    {
        public string GetValue(IMemory memory, ILogger logger, TwoDA twoda, TwoDARow? row, string? columnHeader)
        {
            if (columnHeader == null)
                throw new ArgumentException("HighestValue.GetValue called in an illegal context");

            var cells = twoda.GetCellsUnderColumn(columnHeader);
            IEnumerable<int> integers = cells.Select(x =>
            {
                int integer = -1;
                int.TryParse(x, out integer);
                return integer;
            });
            var highest = integers.Max();
            var next = highest + 1;
            return next.ToString();
        }
    }
}
