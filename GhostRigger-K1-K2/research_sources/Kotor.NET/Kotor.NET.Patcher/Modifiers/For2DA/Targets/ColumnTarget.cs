using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Targets
{
    /// <summary>
    /// Searches for a row in a TwoDA class that matches the stored cell value.
    /// </summary>
    public class ColumnTarget : ITarget
    {
        /// <summary>
        /// 
        /// </summary>
        public string ColumnHeader { get; set; }
        public string CellValue { get; set; }

        public ColumnTarget(string columnHeader, string cellValue)
        {
            ColumnHeader = columnHeader;
            CellValue = cellValue;
        }

        public TwoDARow Search(TwoDA twoda)
        {
            var row = twoda.Rows().SingleOrDefault(x => x.GetCell(ColumnHeader) == CellValue);

            if (row is not null)
            {
                return row;
            }
            else
            {
                throw new ApplyModifierException($"Could not find value {CellValue} at under column {ColumnHeader}.");
            }
        }
    }
}
