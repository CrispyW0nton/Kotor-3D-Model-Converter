using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Patcher.Modifiers.For2DA.Targets
{
    /// <summary>
    /// Searches for a row in a TwoDA class that matches a stored row index.
    /// </summary>
    public class RowIndexTarget : ITarget
    {
        /// <summary>
        /// The row index that will be searched for.
        /// </summary>
        public int RowIndex { get; set; }

        public RowIndexTarget(int rowIndex)
        {
            RowIndex = rowIndex;
        }

        public TwoDARow Search(TwoDA twoda)
        {
            var row = twoda.Row(RowIndex);

            if (row is not null)
            {
                return row;
            }
            else
            {
                throw new ApplyModifierException($"Could not find row at index {RowIndex}.");
            }
        }
    }
}
