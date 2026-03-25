using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Values
{
    /// <summary>
    /// Gets a value under a specific column.
    /// </summary>
    public class CellValue : IValue
    {
        /// <summary>
        /// The column that will be looked at.
        /// </summary>
        public string ColumnHeader { get; set; }

        public CellValue(string columnHeader)
        {
            ColumnHeader = columnHeader;
        }

        public string GetValue(IMemory memory, ILogger logger, TwoDA twoda, TwoDARow? row, string? columnHeader)
        {
            var value = row.GetCell(ColumnHeader);

            if (value is not null)
            {
                return value;
            }
            else
            {
                throw new ApplyModifierException($"Column {ColumnHeader} does not exist.");
            }
        }
    }
}
